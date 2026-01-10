from django.db import migrations
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

def create_groups(apps, schema_editor):
    # We get the models from the versioned app registry (apps)
    # but for Group, Permission, ContentType, it's safe to use the direct import
    # as they are stable parts of Django's auth framework.
    
    # Get content type for the PATD model to find its permissions
    try:
        patd_content_type = ContentType.objects.get(
            app_label='Ouvidoria',
            model='patd'
        )
    except ContentType.DoesNotExist:
        # If this happens, it means the migration is running before the model's table
        # has been created. The dependency on '0046_...' should prevent this.
        print("ContentType for PATD model not found. Skipping group creation.")
        return

    # Get all necessary permissions for the PATD model
    try:
        add_patd_perm = Permission.objects.get(codename='add_patd', content_type=patd_content_type)
        change_patd_perm = Permission.objects.get(codename='change_patd', content_type=patd_content_type)
        delete_patd_perm = Permission.objects.get(codename='delete_patd', content_type=patd_content_type)
        view_patd_perm = Permission.objects.get(codename='view_patd', content_type=patd_content_type)
    except Permission.DoesNotExist:
        # This would be unusual if the model has been migrated.
        print("One or more standard permissions for PATD model not found. Skipping group creation.")
        return

    # --- Define groups and their permissions ---

    # S2 and CB have the same PATD permissions
    s2_cb_perms = [add_patd_perm, change_patd_perm, view_patd_perm]
    
    # ADJUNTO and Chefe have delete permission as well
    adjunto_chefe_perms = [add_patd_perm, change_patd_perm, view_patd_perm, delete_patd_perm]

    groups_to_create = {
        "S2 - Ouvidoria": s2_cb_perms,
        "CB - Ouvidoria": s2_cb_perms,
        "ADJUNTO - Ouvidoria": adjunto_chefe_perms,
        "Chefe - Ouvidoria": adjunto_chefe_perms,
    }

    for group_name, permissions_list in groups_to_create.items():
        group, created = Group.objects.get_or_create(name=group_name)
        if created:
            group.permissions.set(permissions_list)
            print(f"Group '{group_name}' created and permissions assigned.")
        else:
            # If group exists, still ensure its permissions are correct
            group.permissions.set(permissions_list)
            print(f"Group '{group_name}' already existed. Ensured permissions are set correctly.")


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0046_alter_configuracao_comandante_bagl_and_more'),
        # Add dependency on contenttypes to ensure it's available
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(create_groups),
    ]

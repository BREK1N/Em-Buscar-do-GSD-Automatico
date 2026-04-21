from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove Notificacao do estado do ORM em Secao_pessoal sem dropar a tabela.
    O model foi movido para o app caixa_entrada que reutiliza a mesma tabela
    via Meta.db_table = 'Secao_pessoal_notificacao'.
    """

    dependencies = [
        ('Secao_pessoal', '0020_notificacao_anexo'),
        ('caixa_entrada', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel('Notificacao'),
            ],
            database_operations=[],  # Não dropar a tabela
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0076_configuracao_fonte_padrao_documentos_and_more'),
        ('Secao_pessoal', '0024_alter_efetivo_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracao',
            name='oficial_chefe_ouvidoria',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='configuracao_oficial_chefe',
                limit_choices_to={'oficial': True},
                to='Secao_pessoal.efetivo',
                verbose_name='Oficial Chefe da Ouvidoria',
            ),
        ),
        migrations.AddField(
            model_name='patd',
            name='oficial_assinou_analise',
            field=models.BooleanField(default=False, verbose_name='Oficial assinou análise'),
        ),
        migrations.AlterField(
            model_name='patd',
            name='status',
            field=models.CharField(
                choices=[
                    ('definicao_oficial', 'Aguardando definição do Oficial'),
                    ('aguardando_aprovacao_atribuicao', 'Aguardando aprovação de atribuição de oficial'),
                    ('confeccao_fr_ficha', 'Confecção / FR e Ficha Individual'),
                    ('ciencia_militar', 'Aguardando ciência do militar'),
                    ('aguardando_justificativa', 'Aguardando Justificativa'),
                    ('prazo_expirado', 'Prazo expirado'),
                    ('preclusao', 'Preclusão - Sem Defesa'),
                    ('em_apuracao', 'Em Apuração'),
                    ('apuracao_preclusao', 'Em Apuração (Preclusão)'),
                    ('aguardando_punicao', 'Aguardando Aplicação da Punição'),
                    ('aguardando_punicao_alterar', 'Aguardando Punição (alterar)'),
                    ('analise_oficial_apurador', 'Análise do Oficial Apurador'),
                    ('analise_comandante', 'Em Análise pelo Comandante'),
                    ('aguardando_assinatura_npd', 'Aguardando Assinatura NPD'),
                    ('periodo_reconsideracao', 'Período de Reconsideração'),
                    ('em_reconsideracao', 'Em Reconsideração'),
                    ('aguardando_nova_punicao', 'Aguardando nova punição'),
                    ('aguardando_publicacao', 'Aguardando publicação'),
                    ('finalizado', 'Finalizado'),
                ],
                db_index=True,
                default='confeccao_fr_ficha',
                max_length=50,
                verbose_name='Status',
            ),
        ),
    ]

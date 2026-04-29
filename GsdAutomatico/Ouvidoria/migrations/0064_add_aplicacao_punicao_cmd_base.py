from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Ouvidoria', '0063_alter_anexo_tipo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patd',
            name='status',
            field=models.CharField(
                choices=[
                    ('definicao_oficial', 'Definição do Oficial'),
                    ('aguardando_aprovacao_atribuicao', 'Aguardando Aprovação de Atribuição'),
                    ('ciencia_militar', 'Ciência do Militar'),
                    ('aguardando_justificativa', 'Aguardando Justificativa'),
                    ('prazo_expirado', 'Prazo Expirado'),
                    ('preclusao', 'Preclusão'),
                    ('em_apuracao', 'Em Apuração'),
                    ('apuracao_preclusao', 'Apuração por Preclusão'),
                    ('aguardando_punicao', 'Aguardando Punição'),
                    ('aguardando_punicao_alterar', 'Aguardando Punição (Alterar)'),
                    ('aplicacao_punicao_cmd_base', 'Aplicação da Punição – CMD da Base'),
                    ('analise_comandante', 'Análise do Comandante'),
                    ('aguardando_assinatura_npd', 'Aguardando Assinatura NPD'),
                    ('periodo_reconsideracao', 'Período de Reconsideração'),
                    ('em_reconsideracao', 'Em Reconsideração'),
                    ('aguardando_comandante_base', 'Aguardando Comandante Base'),
                    ('aguardando_nova_punicao', 'Aguardando Nova Punição'),
                    ('aguardando_preenchimento_npd_reconsideracao', 'Aguardando Preenchimento NPD Reconsideração'),
                    ('aguardando_publicacao', 'Aguardando Publicação'),
                    ('finalizado', 'Finalizado'),
                ],
                default='definicao_oficial',
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='anexo',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('defesa', 'Defesa'),
                    ('reconsideracao', 'Reconsideração'),
                    ('reconsideracao_oficial', 'Reconsideração Oficial'),
                    ('assinatura_ciencia', 'Assinatura de Ciência'),
                    ('oficio_lancamento', 'Ofício de Lançamento'),
                    ('ficha_individual', 'Ficha Individual'),
                    ('formulario_resumo', 'Formulário de Resumo'),
                    ('documento_final', 'Documento Final Completo'),
                    ('relatorio_delta_base', 'Relatório Delta – CMD da Base'),
                ],
                max_length=30,
            ),
        ),
    ]

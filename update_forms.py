import os

filepath = 'GsdAutomatico/Secao_operacoes/forms.py'
with open(filepath, 'r') as f:
    content = f.read()

new_clean = """
    def clean(self):
        cleaned_data = super().clean()
        militar = cleaned_data.get('militar')
        data = cleaned_data.get('data')
        escala = self.instance.escala if self.instance.pk else None
        
        # Como o form é criado no view passando o escala_id mas ele nao foi injetado na instance ainda:
        # Pelo visto, o model TurnoEscala recebe a escala na view, depois do commit=False.
        # Então precisamos verificar na view ou adicionar escala_id no clean.
"""
print("ok")

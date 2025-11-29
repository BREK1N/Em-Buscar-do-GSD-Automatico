# Verifica se o host do banco de dados está disponível
if [ "$DATABASE" = "postgres" ]
then
    echo "Aguardando pelo PostgreSQL..."

    while ! nc -z $HOST $PORT; do
      sleep 0.1
    done

    echo "PostgreSQL iniciado"
fi

# Roda as migrações do banco de dados
echo "Aplicando migrações..."
python manage.py migrate

# Coleta arquivos estáticos
echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Inicia o servidor usando Waitress (já que está no seu requirements.txt)
echo "Iniciando servidor Waitress..."
exec waitress-serve --listen=*:8000 GsdAutomatico.wsgi:application
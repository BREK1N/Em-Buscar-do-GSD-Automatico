# load_test.ps1 — executa load test contra o Portal GSD
# Uso: .\load_test.ps1 [-Usuarios 50] [-Taxa 5] [-Duracao "2m"] [-Headless]

param(
    [int]$Usuarios   = 30,
    [int]$Taxa       = 3,
    [string]$Duracao = "3m",
    [switch]$Headless,
    [string]$Host    = "http://localhost:8080",
    [string]$User    = "admin",
    [string]$Senha   = "admin"
)

# Verifica se locust está instalado
if (-not (Get-Command locust -ErrorAction SilentlyContinue)) {
    Write-Host "Locust nao encontrado. Instalando..." -ForegroundColor Yellow
    pip install locust
}

$env:GSD_USER     = $User
$env:GSD_PASSWORD = $Senha

if ($Headless) {
    Write-Host ""
    Write-Host "Iniciando load test HEADLESS" -ForegroundColor Cyan
    Write-Host "  Host     : $Host"
    Write-Host "  Usuarios : $Usuarios"
    Write-Host "  Taxa     : $Taxa usuarios/s"
    Write-Host "  Duracao  : $Duracao"
    Write-Host ""
    locust -f locustfile.py `
        --host=$Host `
        --users=$Usuarios `
        --spawn-rate=$Taxa `
        --run-time=$Duracao `
        --headless `
        --html=load_test_report.html
    Write-Host ""
    Write-Host "Relatorio salvo em load_test_report.html" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Iniciando Locust UI em http://localhost:8089" -ForegroundColor Cyan
    Write-Host "  Abra o browser e configure o teste la."
    Write-Host "  Ctrl+C para parar."
    Write-Host ""
    locust -f locustfile.py --host=$Host
}

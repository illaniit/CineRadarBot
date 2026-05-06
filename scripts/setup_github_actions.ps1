param(
    [string]$Repo = ""
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "No encuentro '$Name'. Instala GitHub CLI desde https://cli.github.com/ y ejecuta 'gh auth login'."
    }
}

function Get-Repo {
    param([string]$CurrentRepo)
    if ($CurrentRepo) {
        return $CurrentRepo
    }

    $remoteUrl = ""
    try {
        $remoteUrl = git remote get-url origin 2>$null
    } catch {
        $remoteUrl = ""
    }

    if ($remoteUrl -match "github\.com[:/](?<owner>[^/]+)/(?<repo>[^/.]+)(\.git)?$") {
        return "$($Matches.owner)/$($Matches.repo)"
    }

    return Read-Host "Repositorio GitHub en formato owner/repo"
}

function Read-SecretPlainText {
    param([string]$Name)
    $secure = Read-Host "Valor para secret $Name" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Set-RepoSecret {
    param(
        [string]$RepoFullName,
        [string]$Name
    )
    $plain = Read-SecretPlainText $Name
    try {
        $plain | gh secret set $Name --repo $RepoFullName
    } finally {
        $plain = $null
    }
}

function Set-RepoVariable {
    param(
        [string]$RepoFullName,
        [string]$Name,
        [string]$Value
    )
    gh variable set $Name --repo $RepoFullName --body $Value
}

Require-Command "git"
Require-Command "gh"

$repoFullName = Get-Repo $Repo
if (-not $repoFullName) {
    throw "Hace falta el repositorio en formato owner/repo."
}

Write-Host "Configurando secrets en $repoFullName..."
Set-RepoSecret $repoFullName "TELEGRAM_BOT_TOKEN"
Set-RepoSecret $repoFullName "TELEGRAM_CHAT_ID"
Set-RepoSecret $repoFullName "TMDB_API_TOKEN"
Set-RepoSecret $repoFullName "TMDB_API_KEY"
Set-RepoSecret $repoFullName "STREAMING_API_KEY"

Write-Host "Configurando variables no sensibles..."
Set-RepoVariable $repoFullName "STREAMING_API_PROVIDER" "watchmode"
Set-RepoVariable $repoFullName "COUNTRY" "ES"
Set-RepoVariable $repoFullName "LANGUAGE" "es-ES"
Set-RepoVariable $repoFullName "DAYS_AHEAD" "7"
Set-RepoVariable $repoFullName "MIN_TMDB_VOTE_COUNT" "0"
Set-RepoVariable $repoFullName "MAX_ITEMS_PER_MESSAGE" "8"
Set-RepoVariable $repoFullName "MAX_STREAMING_PAGES" "3"

Write-Host "Listo. Ya puedes lanzar el workflow manualmente desde GitHub Actions."

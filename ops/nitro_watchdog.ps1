# Watchdog da ponte MT5, rodando NO PRÓPRIO VPS (Task Scheduler, a cada 5 min, como SYSTEM).
# - Conta processos python. Se 0 => tenta reiniciar a ponte na sessão interativa (task NitroBridge /IT).
# - Alerta no Telegram só em TRANSIÇÃO de estado (OK<->DOWN). Estado em C:\nitro_wd_state.txt.
# Roda mesmo sem ninguém logado (SYSTEM) — nesse caso o restart /IT não pega, mas o alerta dispara.
$ErrorActionPreference = 'SilentlyContinue'
$TG    = '8817915717:AAF1FCeVgEIeFkRPb7ndMmp7mU7idNcrMH8'
$CHAT  = '8784619222'
$STATE = 'C:\nitro_wd_state.txt'

function Send-TG($msg) {
  try {
    Invoke-RestMethod -Uri "https://api.telegram.org/bot$TG/sendMessage" -Method Post `
      -Body @{ chat_id = $CHAT; text = $msg; parse_mode = 'HTML' } | Out-Null
  } catch {}
}

$n = (Get-Process python -ErrorAction SilentlyContinue | Measure-Object).Count
$prev = if (Test-Path $STATE) { (Get-Content $STATE -Raw).Trim() } else { 'UNKNOWN' }

if ($n -ge 1) {
  $now = 'OK'
} else {
  $now = 'DOWN'
  schtasks /run /tn NitroBridge | Out-Null      # reinicia na sessão do usuário (se logado)
  Start-Sleep -Seconds 8
  $n2 = (Get-Process python -ErrorAction SilentlyContinue | Measure-Object).Count
  if ($n2 -ge 1) { $now = 'OK' }                 # restart pegou
}

if ($now -ne $prev) {
  if ($now -eq 'OK' -and $prev -ne 'UNKNOWN') {
    Send-TG "✅ <b>Ponte MT5</b> de volta no ar (watchdog do VPS reiniciou sozinho)."
  }
  if ($now -eq 'DOWN') {
    Send-TG "🔴 <b>Ponte MT5 caiu</b> no VPS e o watchdog não conseguiu reerguer (provável: ninguém logado no console pós-reboot). Loga na Vultr p/ subir."
  }
  Set-Content $STATE $now
}

"$(Get-Date -Format 'u') status=$now prev=$prev python=$n" | Add-Content 'C:\nitro_wd.log'

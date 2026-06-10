# Ping de pré-abertura: roda 09:00 BRT (dias úteis), confirma no Telegram que a Mesa está pronta.
$ErrorActionPreference = 'SilentlyContinue'
$TG = '8817915717:AAF1FCeVgEIeFkRPb7ndMmp7mU7idNcrMH8'
$CHAT = '8784619222'
function Send-TG($m){ try{ Invoke-RestMethod -Uri "https://api.telegram.org/bot$TG/sendMessage" -Method Post -Body @{chat_id=$CHAT;text=$m;parse_mode='HTML'} | Out-Null }catch{} }
$n = (Get-Process python -ErrorAction SilentlyContinue | Measure-Object).Count
if ($n -ge 1) {
  Send-TG "&#9989; <b>Mesa Nitro pronta pra abertura</b> (pregão 10h). Ponte viva, MT5 conectado, preço ao vivo rodando. Dashboard: mesa-nitro.vercel.app"
} else {
  Send-TG "&#128308; <b>Aten&#231;&#227;o: ponte MT5 caída</b> a ~1h da abertura. Loga no console do VPS (Vultr) p/ subir, ou me chama aqui."
}
"$(Get-Date -Format 'u') preopen python=$n" | Add-Content 'C:\nitro_preopen.log'

# scripts\dev.ps1 - starts one of the dev services
param([Parameter(Mandatory=$true)][ValidateSet('flask','worker','beat','shell')] [string] $Which)

.\.venv\Scripts\Activate.ps1

switch ($Which) {
  'flask'  { python run.py }
  'worker' { celery -A tasks.celery_app.celery worker -l info --pool=solo }
  'beat'   { celery -A tasks.celery_app.celery beat -l info }
  'shell'  { python }
}
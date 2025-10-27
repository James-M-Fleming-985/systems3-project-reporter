from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
from app.models import *
from app.config import settings
from app.exceptions import FeatureDisabledException

lines_db = {}
batches_db = {}
parameters_db = {}
reports_db = {}
alerts_db = {}
maintenance_db = {}

def check_feature_001():
    if not settings.feature_003_001_enabled:
        raise FeatureDisabledException("FEATURE-003-001")

def check_feature_002():
    if not settings.feature_003_002_enabled:
        raise FeatureDisabledException("FEATURE-003-002")

def check_feature_003():
    if not settings.feature_003_003_enabled:
        raise FeatureDisabledException("FEATURE-003-003")

def check_feature_004():
    if not settings.feature_003_004_enabled:
        raise FeatureDisabledException("FEATURE-003-004")

def check_feature_005():
    if not settings.feature_003_005_enabled:
        raise FeatureDisabledException("FEATURE-003-005")

def check_feature_006():
    if not settings.feature_003_006_enabled:
        raise FeatureDisabledException("FEATURE-003-006")

router_001 = APIRouter(dependencies=[Depends(check_feature_001)])
router_002 = APIRouter(dependencies=[Depends(check_feature_002)])
router_003 = APIRouter(dependencies=[Depends(check_feature_003)])
router_004 = APIRouter(dependencies=[Depends(check_feature_004)])
router_005 = APIRouter(dependencies=[Depends(check_feature_005)])
router_006 = APIRouter(dependencies=[Depends(check_feature_006)])

@router_001.get("/lines", response_model=List[Line])
async def get_lines():
    return list(lines_db.values())

@router_001.post("/lines", response_model=Line)
async def create_line(line: Line):
    lines_db[line.id] = line
    return line

@router_001.put("/lines/{line_id}/status")
async def update_line_status(line_id: str, status: LineStatus):
    if line_id not in lines_db:
        raise HTTPException(404, "Line not found")
    lines_db[line_id].status = status
    return lines_db[line_id]

@router_002.get("/batches", response_model=List[Batch])
async def get_batches():
    return list(batches_db.values())

@router_002.post("/batches", response_model=Batch)
async def create_batch(batch: Batch):
    batches_db[batch.id] = batch
    if batch.line_id in lines_db:
        lines_db[batch.line_id].current_batch_id = batch.id
    return batch

@router_002.put("/batches/{batch_id}/complete")
async def complete_batch(batch_id: str):
    if batch_id not in batches_db:
        raise HTTPException(404, "Batch not found")
    batches_db[batch_id].status = BatchStatus.COMPLETED
    batches_db[batch_id].end_time = datetime.now()
    return batches_db[batch_id]

@router_003.get("/parameters", response_model=List[Parameter])
async def get_parameters():
    return list(parameters_db.values())

@router_003.post("/parameters", response_model=Parameter)
async def create_parameter(parameter: Parameter):
    parameters_db[parameter.id] = parameter
    return parameter

@router_003.get("/parameters/batch/{batch_id}")
async def get_batch_parameters(batch_id: str):
    return [p for p in parameters_db.values() if p.batch_id == batch_id]

@router_004.get("/reports", response_model=List[Report])
async def get_reports():
    return list(reports_db.values())

@router_004.post("/reports/generate/{batch_id}")
async def generate_report(batch_id: str):
    if batch_id not in batches_db:
        raise HTTPException(404, "Batch not found")
    report = Report(
        id=f"report_{len(reports_db) + 1}",
        batch_id=batch_id,
        generated_at=datetime.now(),
        data={"batch": batches_db[batch_id].dict()}
    )
    reports_db[report.id] = report
    return report

@router_004.get("/reports/{report_id}")
async def get_report(report_id: str):
    if report_id not in reports_db:
        raise HTTPException(404, "Report not found")
    return reports_db[report_id]

@router_005.get("/alerts", response_model=List[Alert])
async def get_alerts():
    return list(alerts_db.values())

@router_005.post("/alerts", response_model=Alert)
async def create_alert(alert: Alert):
    alerts_db[alert.id] = alert
    return alert

@router_005.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    if alert_id not in alerts_db:
        raise HTTPException(404, "Alert not found")
    alerts_db[alert_id].acknowledged = True
    return alerts_db[alert_id]

@router_006.get("/maintenance", response_model=List[Maintenance])
async def get_maintenance():
    return list(maintenance_db.values())

@router_006.post("/maintenance", response_model=Maintenance)
async def schedule_maintenance(maintenance: Maintenance):
    maintenance_db[maintenance.id] = maintenance
    return maintenance

@router_006.put("/maintenance/{maintenance_id}/complete")
async def complete_maintenance(maintenance_id: str):
    if maintenance_id not in maintenance_db:
        raise HTTPException(404, "Maintenance not found")
    maintenance_db[maintenance_id].completed = True
    return maintenance_db[maintenance_id]
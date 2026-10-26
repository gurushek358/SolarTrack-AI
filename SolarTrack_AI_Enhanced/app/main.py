from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
from io import BytesIO
import math, random, csv, io

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="SolarTrack AI", version="3.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

PANEL_TYPES = {
    "monocrystalline": {"label":"Monocrystalline silicon", "efficiency":22.0, "module_w":450, "temp_coeff":-0.30, "lifespan":30, "cost_per_kw":850, "color":"High efficiency", "note":"Good output per roof area; usually a premium option."},
    "p-type_mono": {"label":"P-type monocrystalline PERC", "efficiency":21.0, "module_w":420, "temp_coeff":-0.34, "lifespan":25, "cost_per_kw":720, "color":"Mainstream value", "note":"Common cost-effective residential technology."},
    "polycrystalline": {"label":"Polycrystalline silicon", "efficiency":17.0, "module_w":330, "temp_coeff":-0.39, "lifespan":25, "cost_per_kw":620, "color":"Budget / legacy", "note":"Generally needs more area for the same rated capacity."},
    "topcon": {"label":"N-type TOPCon", "efficiency":23.0, "module_w":460, "temp_coeff":-0.29, "lifespan":30, "cost_per_kw":900, "color":"Modern high output", "note":"High efficiency with good temperature performance; model-dependent."},
    "hjt": {"label":"Heterojunction (HJT)", "efficiency":23.5, "module_w":460, "temp_coeff":-0.26, "lifespan":30, "cost_per_kw":980, "color":"Premium / low temp loss", "note":"Often strong temperature performance; check product datasheet."},
    "thin_film": {"label":"Thin-film (CdTe/CIGS family)", "efficiency":18.0, "module_w":350, "temp_coeff":-0.28, "lifespan":25, "cost_per_kw":680, "color":"Specialized applications", "note":"Performance and use case vary substantially by thin-film technology."}
}
state = {"tick":0, "soc":72.0, "used_today":4.1, "daily_allowance":12.0,
         "battery_capacity":10.0, "tilt":18, "azimuth":180, "system_kw":5.0,
         "panel_type":"topcon", "fault":"none"}
appliances = [
    {"name":"Refrigerator","watts":150,"icon":"🧊","hours":24},
    {"name":"Air conditioner","watts":900,"icon":"❄️","hours":5},
    {"name":"Lighting","watts":120,"icon":"💡","hours":6},
    {"name":"Television","watts":110,"icon":"📺","hours":4},
    {"name":"Laptop & devices","watts":100,"icon":"💻","hours":7},
    {"name":"Water pump","watts":500,"icon":"🚿","hours":0.7},
]
history, notifications, last_alerts = [], [], set()
def snapshot():
    state["tick"] += 1
    phase = (state["tick"] % 120) / 120
    daylight = max(0.05, math.sin(phase * math.pi))
    panel = PANEL_TYPES[state["panel_type"]]
    temp = 24 + 17 * daylight + random.uniform(-2.2, 2.2)
    irradiance = max(40, 950 * daylight * random.uniform(.82, 1.06))
    base = state["system_kw"] * daylight * random.uniform(.84, 1.02)
    temp_factor = max(.72, 1 + (temp - 25) * panel["temp_coeff"] / 100)
    fault_factor = {"none":1.0,"soiling":.82,"partial_shading":.65,"hotspot":.72,"inverter_issue":.48,"sensor_anomaly":1.0}[state["fault"]]
    solar = max(.02, base * temp_factor * fault_factor)
    load = max(.30, 1.65 * random.uniform(.82, 1.2))
    net = solar - load
    state["soc"] = max(8, min(100, state["soc"] + net * .08))
    state["used_today"] = min(state["daily_allowance"], state["used_today"] + load / 1800)
    backup = (state["battery_capacity"] * state["soc"] / 100) / max(load, .1)
    rec_tilt = 12 if daylight > .72 else 18
    anomaly = min(99, max(3, abs(temp-34)*2 + (1-fault_factor)*100 + random.uniform(0,8)))
    data = {
      "timestamp":datetime.now().strftime("%H:%M:%S"), "solar_kw":round(solar,2), "house_kw":round(load,2),
      "grid_kw":round(max(0,load-solar),2), "surplus_kw":round(max(0,solar-load),2),
      "battery_flow_kw":round(net,2), "soc":round(state["soc"],1),
      "battery_kwh":round(state["battery_capacity"]*state["soc"]/100,2), "battery_capacity":state["battery_capacity"],
      "backup_hours":round(backup,1), "used_today":round(state["used_today"],2),
      "remaining_allowance":round(max(0,state["daily_allowance"]-state["used_today"]),2),
      "daily_allowance":state["daily_allowance"], "tilt":state["tilt"], "azimuth":state["azimuth"],
      "recommended_tilt":rec_tilt, "recommended_azimuth":180, "panel_temp":round(temp,1),
      "irradiance":round(irradiance), "anomaly_score":round(anomaly), "fault":state["fault"],
      "panel_type":state["panel_type"], "panel":panel, "system_kw":state["system_kw"],
      "estimated_panel_count":math.ceil(state["system_kw"]*1000/panel["module_w"]),
      "estimated_output_at_stc_kw":round(state["system_kw"],2),
      "estimated_area_m2":round(state["system_kw"]*1000/(panel["efficiency"]*10),1),
      "estimated_cost":round(state["system_kw"]*panel["cost_per_kw"]),
      "appliances":[{**a,"current_kw":round(a["watts"]/1000*random.uniform(.82,1.12),2),
                     "daily_kwh":round(a["watts"]*a["hours"]/1000,2)} for a in appliances]
    }
    history.append({k:data[k] for k in ("timestamp","solar_kw","house_kw","soc","panel_temp","anomaly_score","grid_kw","surplus_kw","irradiance")})
    if len(history)>90: history.pop(0)
    check_alerts(data)
    return data
def check_alerts(d):
    checks=[
      ("high_load",d["house_kw"]>2.0,"High household demand",f"Household load is {d['house_kw']:.2f} kW."),
      ("low_soc",d["soc"]<25,"Low battery charge",f"Battery state of charge is {d['soc']:.0f}%."),
      ("grid_import",d["grid_kw"]>.5,"Grid support needed",f"Estimated grid import {d['grid_kw']:.2f} kW."),
      ("budget",d["remaining_allowance"]<2,"Energy budget running low",f"Only {d['remaining_allowance']:.2f} kWh remains in the demo allowance."),
      ("fault",d["fault"]!="none","Simulated panel/system fault",f"Demo fault selected: {d['fault'].replace('_',' ')}.")
    ]
    for key,active,title,message in checks:
        if active and key not in last_alerts:
            notifications.insert(0,{"time":d["timestamp"],"title":title,"message":message,"level":"warning"})
            last_alerts.add(key)
        elif not active: last_alerts.discard(key)
    del notifications[30:]

@app.get("/", response_class=HTMLResponse)
def home(): return (ROOT/"static"/"index.html").read_text(encoding="utf-8")
@app.get("/api/live")
def live(): return snapshot()
@app.get("/api/history")
def get_history(): return {"history":history}
@app.get("/api/notifications")
def get_notifications(): return {"notifications":notifications}
@app.get("/api/panels")
def panels(): return {"panel_types":PANEL_TYPES,"selected":state["panel_type"],"system_kw":state["system_kw"]}
class Settings(BaseModel):
    panel_type: str | None = None
    system_kw: float | None = None
    fault: str | None = None
    tilt: int | None = None
    azimuth: int | None = None
@app.post("/api/settings")
def set_settings(req:Settings):
    if req.panel_type is not None:
        if req.panel_type not in PANEL_TYPES: return {"error":"Unknown panel type"}
        state["panel_type"]=req.panel_type
    if req.system_kw is not None: state["system_kw"]=max(0.5,min(100,float(req.system_kw)))
    if req.fault is not None:
        if req.fault not in {"none","soiling","partial_shading","hotspot","inverter_issue","sensor_anomaly"}: return {"error":"Unknown fault"}
        state["fault"]=req.fault
    if req.tilt is not None: state["tilt"]=max(0,min(90,int(req.tilt)))
    if req.azimuth is not None: state["azimuth"]=max(0,min(359,int(req.azimuth)))
    return {"ok":True,"settings":state}
@app.post("/api/reset")
def reset_demo():
    state.update({"soc":72.0,"used_today":4.1,"fault":"none"})
    notifications.clear(); last_alerts.clear()
    return {"ok":True}
class ChatRequest(BaseModel): message:str
@app.post("/api/chat")
def chat(req:ChatRequest):
    q=req.message.lower(); d=snapshot()
    if any(x in q for x in ["tilt","direction","angle","track","orientation"]):
        answer=f"Demo guidance: tilt {d['recommended_tilt']}° and azimuth {d['recommended_azimuth']}°. This is illustrative, not a physical tracker command."
    elif any(x in q for x in ["battery","backup","charge","soc"]):
        answer=f"Battery {d['soc']:.1f}% ({d['battery_kwh']:.2f} kWh estimated); at current load, backup estimate is {d['backup_hours']:.1f} hours."
    elif any(x in q for x in ["appliance","device","consume","consumption","which uses"]):
        top=sorted(d["appliances"],key=lambda a:a["daily_kwh"],reverse=True)
        answer="Estimated daily use: "+", ".join(f"{a['name']} {a['daily_kwh']:.2f} kWh" for a in top[:4])+". Demo estimates, not meter readings."
    elif any(x in q for x in ["remaining","left","budget","allowance"]):
        answer=f"Estimated demo allowance remaining: {d['remaining_allowance']:.2f} kWh of {d['daily_allowance']:.1f} kWh."
    elif any(x in q for x in ["fault","alert","notification","problem","anomaly"]):
        answer=f"Selected demo fault: {d['fault']}. Anomaly indicator {d['anomaly_score']}/100. There are {len(notifications)} recent notifications."
    elif any(x in q for x in ["panel","type","efficiency","module"]):
        p=d["panel"]; answer=f"Selected panel: {p['label']}; representative efficiency {p['efficiency']}%, module rating {p['module_w']} W, temperature coefficient {p['temp_coeff']}%/°C. Check manufacturer datasheet for exact values."
    elif any(x in q for x in ["generation","solar","power","energy"]):
        answer=f"Current simulated solar generation {d['solar_kw']:.2f} kW; household demand {d['house_kw']:.2f} kW; grid import {d['grid_kw']:.2f} kW."
    else:
        answer="Ask me about solar generation, panel technology/specifications, battery backup, appliance estimates, tracker guidance, energy budget, faults, or anomaly score."
    return {"answer":answer}
@app.get("/api/report.csv")
def csv_report():
    d=snapshot(); s=io.StringIO(); w=csv.writer(s)
    w.writerow(["SolarTrack AI demo report",datetime.now().isoformat()]); w.writerow(["Metric","Value","Unit"])
    for label,key,unit in [("Solar generation","solar_kw","kW"),("Household load","house_kw","kW"),("Grid import","grid_kw","kW"),("Battery SOC","soc","%"),
      ("Stored battery energy","battery_kwh","kWh"),("Backup estimate","backup_hours","hours"),("Energy used today","used_today","kWh"),
      ("Remaining demo allowance","remaining_allowance","kWh"),("Panel temperature","panel_temp","°C"),("Irradiance","irradiance","W/m²"),("Anomaly score","anomaly_score","/100")]:
        w.writerow([label,d[key],unit])
    w.writerow(["Panel type",d["panel"]["label"]]); w.writerow(["System size",d["system_kw"],"kW"])
    w.writerow([]); w.writerow(["Appliance","Rated watts","Estimated kWh/day"])
    for a in d["appliances"]: w.writerow([a["name"],a["watts"],a["daily_kwh"]])
    return StreamingResponse(iter([s.getvalue().encode("utf-8-sig")]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=solartrack_report.csv"})
@app.get("/api/report.pdf")
def pdf_report():
    d=snapshot()
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4); styles=getSampleStyleSheet()
        story=[Paragraph("SolarTrack AI — Energy Report",styles["Title"]),Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · Simulated readings",styles["Normal"]),Spacer(1,12)]
        p=d["panel"]
        rows=[["Metric","Reading"],["Solar generation",f"{d['solar_kw']:.2f} kW"],["Household load",f"{d['house_kw']:.2f} kW"],["Grid import",f"{d['grid_kw']:.2f} kW"],
          ["Battery SOC",f"{d['soc']:.1f}%"],["Stored energy",f"{d['battery_kwh']:.2f} kWh"],["Backup estimate",f"{d['backup_hours']:.1f} h"],
          ["Panel technology",p["label"]],["Panel efficiency",f"{p['efficiency']}% (representative)"],["Module rating",f"{p['module_w']} W (representative)"],
          ["System size",f"{d['system_kw']:.1f} kW"],["Panel temperature",f"{d['panel_temp']:.1f} °C"],["Anomaly score",f"{d['anomaly_score']}/100"]]
        t=Table(rows,hAlign="LEFT"); t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12304a")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.grey),("PADDING",(0,0),(-1,-1),6)])); story += [t,Spacer(1,12),Paragraph("Appliance estimates",styles["Heading2"])]
        ar=[["Appliance","Rated W","Estimated kWh/day"]]+[[a["name"],str(a["watts"]),f"{a['daily_kwh']:.2f}"] for a in d["appliances"]]
        at=Table(ar,hAlign="LEFT"); at.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dcefe8")),("GRID",(0,0),(-1,-1),.4,colors.grey),("PADDING",(0,0),(-1,-1),5)])); story += [at,Spacer(1,10),Paragraph("Disclaimer: all readings are simulated. Panel specs are representative examples, not a manufacturer guarantee or engineering assessment.",styles["Italic"])]
        doc.build(story); buf.seek(0)
        return StreamingResponse(buf,media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=solartrack_report.pdf"})
    except ImportError: return {"error":"PDF dependency missing. Run: python -m pip install reportlab"}
@app.get("/api/health")
def health(): return {"status":"online","service":"SolarTrack AI","mode":"simulated"}

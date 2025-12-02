#!/usr/bin/env bash
# create_and_zip.sh
# Creates the directory tree and files for the "new files from today"
# and packages them into goose_c2_files.zip
# Usage in iSH:
#   paste this file via heredoc, then:
#   chmod +x create_and_zip.sh
#   ./create_and_zip.sh
set -euo pipefail

# Create directories (idempotent)
mkdir -p backend/workers frontend/src/components

# Write backend/models.py
cat > backend/models.py <<'PYEOF'
# -- C2 Models Extension for GooseStrike --
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON as JSONType
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

c2_agent_asset = Table(
    'c2_agent_asset', Base.metadata,
    Column('agent_id', Integer, ForeignKey('c2_agents.id')),
    Column('asset_id', Integer, ForeignKey('assets.id')),
)

class C2Instance(Base):
    __tablename__ = "c2_instances"
    id = Column(Integer, primary_key=True)
    provider = Column(String)
    status = Column(String)
    last_poll = Column(DateTime)
    error = Column(Text)

class C2Operation(Base):
    __tablename__ = 'c2_operations'
    id = Column(Integer, primary_key=True)
    operation_id = Column(String, unique=True, index=True)
    name = Column(String)
    provider = Column(String)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    description = Column(Text)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    alerts = relationship("C2Event", backref="operation")

class C2Agent(Base):
    __tablename__ = 'c2_agents'
    id = Column(Integer, primary_key=True)
    agent_id = Column(String, unique=True, index=True)
    provider = Column(String)
    name = Column(String)
    operation_id = Column(Integer, ForeignKey("c2_operations.id"), nullable=True)
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    ip_address = Column(String)
    hostname = Column(String)
    platform = Column(String)
    user = Column(String)
    pid = Column(Integer)
    state = Column(String)
    mitre_techniques = Column(JSONType)
    assets = relationship("Asset", secondary=c2_agent_asset, backref="c2_agents")

class C2Event(Base):
    __tablename__ = 'c2_events'
    id = Column(Integer, primary_key=True)
    event_id = Column(String, unique=True, index=True)
    type = Column(String)
    description = Column(Text)
    agent_id = Column(Integer, ForeignKey('c2_agents.id'))
    operation_id = Column(Integer, ForeignKey('c2_operations.id'))
    timestamp = Column(DateTime)
    mitre_tag = Column(String)
    details = Column(JSONType, default=dict)

class C2Payload(Base):
    __tablename__ = "c2_payloads"
    id = Column(Integer, primary_key=True)
    payload_id = Column(String, unique=True)
    provider = Column(String)
    agent_id = Column(String)
    operation_id = Column(String)
    type = Column(String)
    created_at = Column(DateTime)
    filename = Column(String)
    path = Column(String)
    content = Column(Text)

class C2Listener(Base):
    __tablename__ = "c2_listeners"
    id = Column(Integer, primary_key=True)
    listener_id = Column(String, unique=True)
    provider = Column(String)
    operation_id = Column(String)
    port = Column(Integer)
    transport = Column(String)
    status = Column(String)
    created_at = Column(DateTime)

class C2Task(Base):
    __tablename__ = "c2_tasks"
    id = Column(Integer, primary_key=True)
    task_id = Column(String, unique=True, index=True)
    agent_id = Column(String)
    operation_id = Column(String)
    command = Column(Text)
    status = Column(String)
    result = Column(Text)
    created_at = Column(DateTime)
    executed_at = Column(DateTime)
    error = Column(Text)
    mitre_technique = Column(String)
PYEOF

# Write backend/workers/c2_integration.py
cat > backend/workers/c2_integration.py <<'PYEOF'
#!/usr/bin/env python3
# Simplified C2 poller adapters (Mythic/Caldera) — adjust imports for your repo
import os, time, requests, logging
from datetime import datetime
# Import models and Session from your project; this is a placeholder import
try:
    from models import Session, C2Instance, C2Agent, C2Operation, C2Event, C2Payload, C2Listener, C2Task, Asset
except Exception:
    # If using package layout, adapt the import path
    try:
        from backend.models import Session, C2Instance, C2Agent, C2Operation, C2Event, C2Payload, C2Listener, C2Task, Asset
    except Exception:
        # Minimal placeholders to avoid immediate runtime errors during demo
        Session = None
        C2Instance = C2Agent = C2Operation = C2Event = C2Payload = C2Listener = C2Task = Asset = object

from urllib.parse import urljoin

class BaseC2Adapter:
    def __init__(self, base_url, api_token):
        self.base_url = base_url
        self.api_token = api_token

    def api(self, path, method="get", **kwargs):
        url = urljoin(self.base_url, path)
        headers = kwargs.pop("headers", {})
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        try:
            r = getattr(requests, method)(url, headers=headers, timeout=15, **kwargs)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.error(f"C2 API error {url}: {e}")
            return None

    def get_status(self): raise NotImplementedError
    def get_agents(self): raise NotImplementedError
    def get_operations(self): raise NotImplementedError
    def get_events(self, since=None): raise NotImplementedError
    def create_payload(self, op_id, typ, params): raise NotImplementedError
    def launch_command(self, agent_id, cmd): raise NotImplementedError
    def create_listener(self, op_id, port, transport): raise NotImplementedError

class MythicAdapter(BaseC2Adapter):
    def get_status(self): return self.api("/api/v1/status")
    def get_agents(self): return (self.api("/api/v1/agents") or {}).get("agents", [])
    def get_operations(self): return (self.api("/api/v1/operations") or {}).get("operations", [])
    def get_events(self, since=None): return (self.api("/api/v1/events") or {}).get("events", [])
    def create_payload(self, op_id, typ, params):
        return self.api("/api/v1/payloads", "post", json={"operation_id": op_id, "type": typ, "params": params})
    def launch_command(self, agent_id, cmd):
        return self.api(f"/api/v1/agents/{agent_id}/tasks", "post", json={"command": cmd})
    def create_listener(self, op_id, port, transport):
        return self.api("/api/v1/listeners", "post", json={"operation_id": op_id, "port": port, "transport": transport})

class CalderaAdapter(BaseC2Adapter):
    def _caldera_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def get_status(self):
        try:
            r = requests.get(f"{self.base_url}/api/health", headers=self._caldera_headers(), timeout=10)
            return {"provider": "caldera", "status": r.json().get("status", "healthy")}
        except Exception:
            return {"provider": "caldera", "status": "unreachable"}

    def get_agents(self):
        r = requests.get(f"{self.base_url}/api/agents/all", headers=self._caldera_headers(), timeout=15)
        agents = r.json() if r.status_code == 200 else []
        for agent in agents:
            mitre_tids = []
            for ab in agent.get("abilities", []):
                tid = ab.get("attack", {}).get("technique_id")
                if tid:
                    mitre_tids.append(tid)
            agent["mitre"] = mitre_tids
        return [{"id": agent.get("paw"), "name": agent.get("host"), "ip": agent.get("host"), "hostname": agent.get("host"), "platform": agent.get("platform"), "pid": agent.get("pid"), "status": "online" if agent.get("trusted", False) else "offline", "mitre": agent.get("mitre"), "operation": agent.get("operation")} for agent in agents]

    def get_operations(self):
        r = requests.get(f"{self.base_url}/api/operations", headers=self._caldera_headers(), timeout=10)
        ops = r.json() if r.status_code == 200 else []
        return [{"id": op.get("id"), "name": op.get("name"), "start_time": op.get("start"), "description": op.get("description", "")} for op in ops]

    def get_events(self, since_timestamp=None):
        events = []
        ops = self.get_operations()
        for op in ops:
            url = f"{self.base_url}/api/operations/{op['id']}/reports"
            r = requests.get(url, headers=self._caldera_headers(), timeout=15)
            reports = r.json() if r.status_code == 200 else []
            for event in reports:
                evt_time = event.get("timestamp")
                if since_timestamp and evt_time < since_timestamp:
                    continue
                events.append({"id": event.get("id", ""), "type": event.get("event_type", ""), "description": event.get("message", ""), "agent": event.get("paw", None), "operation": op["id"], "time": evt_time, "mitre": event.get("ability_id", None), "details": event})
        return events

    def create_payload(self, operation_id, payload_type, params):
        ability_id = params.get("ability_id")
        if not ability_id:
            return {"error": "ability_id required"}
        r = requests.post(f"{self.base_url}/api/abilities/{ability_id}/create_payload", headers=self._caldera_headers(), json={"operation_id": operation_id})
        j = r.json() if r.status_code == 200 else {}
        return {"id": j.get("id", ""), "filename": j.get("filename", ""), "path": j.get("path", ""), "content": j.get("content", "")}

    def launch_command(self, agent_id, command):
        ability_id = command.get("ability_id")
        cmd_blob = command.get("cmd_blob")
        data = {"ability_id": ability_id}
        if cmd_blob:
            data["cmd"] = cmd_blob
        r = requests.post(f"{self.base_url}/api/agents/{agent_id}/task", headers=self._caldera_headers(), json=data)
        return r.json() if r.status_code in (200,201) else {"error": "failed"}

    def create_listener(self, operation_id, port, transport):
        try:
            r = requests.post(f"{self.base_url}/api/listeners", headers=self._caldera_headers(), json={"operation_id": operation_id, "port": port, "transport": transport})
            return r.json()
        except Exception as e:
            return {"error": str(e)}

def get_c2_adapter():
    provider = os.getenv("C2_PROVIDER", "none")
    url = os.getenv("C2_BASE_URL", "http://c2:7443")
    token = os.getenv("C2_API_TOKEN", "")
    if provider == "mythic":
        return MythicAdapter(url, token)
    if provider == "caldera":
        return CalderaAdapter(url, token)
    return None

class C2Poller:
    def __init__(self, poll_interval=60):
        self.adapter = get_c2_adapter()
        self.poll_interval = int(os.getenv("C2_POLL_INTERVAL", poll_interval or 60))
        self.last_event_poll = None

    def _store(self, instance_raw, agents_raw, operations_raw, events_raw):
        # This function expects a working SQLAlchemy Session and models
        if Session is None:
            return
        db = Session()
        now = datetime.utcnow()
        inst = db.query(C2Instance).first()
        if not inst:
            inst = C2Instance(provider=instance_raw.get("provider"), status=instance_raw.get("status"), last_poll=now)
        else:
            inst.status = instance_raw.get("status")
            inst.last_poll = now
        db.add(inst)

        opmap = {}
        for op_data in operations_raw or []:
            op = db.query(C2Operation).filter_by(operation_id=op_data["id"]).first()
            if not op:
                op = C2Operation(operation_id=op_data["id"], name=op_data.get("name"), provider=inst.provider, start_time=op_data.get("start_time"))
            db.merge(op)
            db.flush()
            opmap[op.operation_id] = op.id

        for agent_data in agents_raw or []:
            agent = db.query(C2Agent).filter_by(agent_id=agent_data["id"]).first()
            if not agent:
                agent = C2Agent(agent_id=agent_data["id"], provider=inst.provider, name=agent_data.get("name"), first_seen=now)
            agent.last_seen = now
            agent.operation_id = opmap.get(agent_data.get("operation"))
            agent.ip_address = agent_data.get("ip")
            agent.state = agent_data.get("status", "unknown")
            agent.mitre_techniques = agent_data.get("mitre", [])
            db.merge(agent)
            db.flush()

        for evt in events_raw or []:
            event = db.query(C2Event).filter_by(event_id=evt.get("id","")).first()
            if not event:
                event = C2Event(event_id=evt.get("id",""), type=evt.get("type",""), description=evt.get("description",""), agent_id=evt.get("agent"), operation_id=evt.get("operation"), timestamp=evt.get("time", now), mitre_tag=evt.get("mitre"), details=evt)
            db.merge(event)
        db.commit()
        db.close()

    def run(self):
        while True:
            try:
                if not self.adapter:
                    time.sleep(self.poll_interval)
                    continue
                instance = self.adapter.get_status()
                agents = self.adapter.get_agents()
                operations = self.adapter.get_operations()
                events = self.adapter.get_events(since=self.last_event_poll)
                self.last_event_poll = datetime.utcnow().isoformat()
                self._store(instance, agents, operations, events)
            except Exception as e:
                print("C2 poll error", e)
            time.sleep(self.poll_interval)

if __name__ == "__main__":
    C2Poller().run()
PYEOF

# Write backend/routes/c2.py
cat > backend/routes_c2_placeholder.py <<'PYEOF'
# Placeholder router. In your FastAPI app, create a router that imports your adapter and DB models.
# This file is a simple reference; integrate into your backend/routes/c2.py as needed.
from fastapi import APIRouter, Request
from datetime import datetime
router = APIRouter()

@router.get("/status")
def c2_status():
    return {"provider": None, "status": "not-configured", "last_poll": None}
PYEOF
mv backend/routes_c2_placeholder.py backend/routes_c2.py

# Create the frontend component file
cat > frontend/src/components/C2Operations.jsx <<'JSEOF'
import React, {useEffect, useState} from "react";
export default function C2Operations() {
  const [status, setStatus] = useState({});
  const [agents, setAgents] = useState([]);
  const [ops, setOps] = useState([]);
  const [events, setEvents] = useState([]);
  const [abilityList, setAbilityList] = useState([]);
  const [showTaskDialog, setShowTaskDialog] = useState(false);
  const [taskAgentId, setTaskAgentId] = useState(null);
  const [activeOp, setActiveOp] = useState(null);

  useEffect(() => {
    fetch("/c2/status").then(r=>r.json()).then(setStatus).catch(()=>{});
    fetch("/c2/operations").then(r=>r.json()).then(ops=>{
      setOps(ops); setActiveOp(ops.length ? ops[0].id : null);
    }).catch(()=>{});
    fetch("/c2/abilities").then(r=>r.json()).then(setAbilityList).catch(()=>{});
  }, []);

  useEffect(() => {
    if (activeOp) {
      fetch(`/c2/agents?operation=${activeOp}`).then(r=>r.json()).then(setAgents).catch(()=>{});
      fetch(`/c2/events?op=${activeOp}`).then(r=>r.json()).then(setEvents).catch(()=>{});
    }
  }, [activeOp]);

  const genPayload = async () => {
    const typ = prompt("Payload type? (beacon/http etc)");
    if (!typ) return;
    const res = await fetch("/c2/payload", {
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({operation_id:activeOp,type:typ,params:{}})
    });
    alert("Payload: " + (await res.text()));
  };
  const createListener = async () => {
    const port = prompt("Port to listen on?");
    const transport = prompt("Transport? (http/smb/etc)");
    if (!port || !transport) return;
    await fetch("/c2/listener",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({operation_id:activeOp,port:Number(port),transport})
    });
    alert("Listener created!");
  };
  const openTaskDialog = (agentId) => {
    setTaskAgentId(agentId);
    setShowTaskDialog(true);
  };
  const handleTaskSend = async () => {
    const abilityId = document.getElementById("caldera_ability_select").value;
    const cmd_blob = document.getElementById("caldera_cmd_input").value;
    await fetch(`/c2/agents/${taskAgentId}/command`, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({command:{ability_id:abilityId, cmd_blob}})
    });
    setShowTaskDialog(false);
    alert("Task sent to agent!");
  };

  const renderMitre = tidList => tidList ? tidList.map(tid=>
    <span style={{border:"1px solid #8cf",borderRadius:4,padding:"2px 4px",margin:"2px",background:"#eeffee"}} key={tid}>{tid}</span>
  ) : null;

  return (
    <div>
      <h2>C2 Operations ({status.provider || 'Unconfigured'})</h2>
      <div>
        <label>Operation:</label>
        <select onChange={e=>setActiveOp(e.target.value)} value={activeOp||""}>{ops.map(op=>
          <option key={op.id} value={op.id}>{op.name}</option>
        )}</select>
        <button onClick={genPayload}>Generate Payload</button>
        <button onClick={createListener}>Create Listener</button>
      </div>
      <div>
        <h3>Agents</h3>
        <table border="1"><thead>
          <tr><th>Agent</th><th>IP</th><th>Hostname</th><th>Status</th><th>MITRE</th><th>Task</th></tr>
        </thead><tbody>
        {agents.map(a=>
          <tr key={a.id}>
            <td>{a.name||a.id}</td>
            <td>{a.ip}</td>
            <td>{a.hostname}</td>
            <td>{a.state}</td>
            <td>{renderMitre(a.mitre_techniques)}</td>
            <td><button onClick={()=>openTaskDialog(a.id)}>Send Cmd</button></td>
          </tr>
        )}
        </tbody></table>
      </div>
      <div>
        <h3>Recent Events</h3>
        <ul>
          {events.map(e=>
            <li key={e.id}>[{e.type}] {e.desc} [Agent:{e.agent} Op:{e.op}] {e.mitre && <b>{e.mitre}</b>} @ {e.time}</li>
          )}
        </ul>
      </div>
      <div>
        <span style={{display:'inline-block',background:'#ffe',border:'1px solid #ec3',padding:4,margin:4}}>⚠️ <b>LAB ONLY: All actions are for simulation/training inside this closed cyber range!</b></span>
      </div>
      {showTaskDialog &&
        <div style={{
          position: "fixed", background: "#fff", top: "20%", left: "40%",
          border: "2px solid #246", borderRadius: 8, padding: 16, zIndex: 10
        }}>
          <h3>Task Agent {taskAgentId} (Caldera)</h3>
          <label>Ability:</label>
          <select id="caldera_ability_select">
            {abilityList.map(ab =>
              <option key={ab.ability_id} value={ab.ability_id}>
                {ab.name} - {ab.attack && ab.attack.technique_id}
              </option>)}
          </select>
          <br />
          <label>Command Blob (optional):</label>
          <input id="caldera_cmd_input" placeholder="bash -c ..."/>
          <br />
          <button onClick={handleTaskSend}>Send</button>
          <button onClick={()=>setShowTaskDialog(false)}>Cancel</button>
        </div>
      }
    </div>
  );
}
JSEOF

# Minimal supporting files
cat > docker-compose.kali.yml <<'YAML'
services:
  api:
    build: ./backend
  ui:
    build: ./frontend
YAML

cat > COMPREHENSIVE_GUIDE.md <<'GUIDE'
# Comprehensive Guide (placeholder)
This is the comprehensive guide placeholder. Replace with full content as needed.
GUIDE

cat > C2-integration-session.md <<'SESSION'
C2 integration session transcript placeholder.
SESSION

cat > README.md <<'RME'
# GooseStrike Cyber Range - placeholder README
RME

# Create a simple package.json to ensure directory present
mkdir -p frontend
cat > frontend/package.json <<'PKG'
{ "name": "goosestrike-frontend", "version": "0.1.0" }
PKG

# Create the zip
ZIPNAME="goose_c2_files.zip"
if command -v zip >/dev/null 2>&1; then
  zip -r "${ZIPNAME}" backend frontend docker-compose.kali.yml COMPREHENSIVE_GUIDE.md C2-integration-session.md README.md >/dev/null
else
  python3 - <<PY3
import zipfile, os
out = "goose_c2_files.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk("backend"):
        for f in files:
            z.write(os.path.join(root, f))
    for root, dirs, files in os.walk("frontend"):
        for f in files:
            z.write(os.path.join(root, f))
    z.write("docker-compose.kali.yml")
    z.write("COMPREHENSIVE_GUIDE.md")
    z.write("C2-integration-session.md")
    z.write("README.md")
print("ZIP created:", out)
PY3
fi

echo "Created goose_c2_files.zip in $(pwd)"
ls -lh goose_c2_files.zip
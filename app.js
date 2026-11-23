const $ = id => document.getElementById(id);
const state = {view:"overview", challenge:null, selectedDevice:null, devices:[], agentUrl:localStorage.getItem("adbAgentUrl")||"http://127.0.0.1:8765", agentToken:localStorage.getItem("adbAgentToken")||""};
$("agentUrl").value=state.agentUrl; $("agentToken").value=state.agentToken;
const navNames = {overview:"Overview",adb:"ADB Console",attestation:"Meta Attestation",diagnostics:"Diagnostics"};
function toast(message, error=false){const el=document.createElement("div");el.className="toast"+(error?" error":"");el.textContent=message;$("toasts").append(el);setTimeout(()=>el.remove(),3800)}
function log(message, kind=""){const el=document.createElement("div");el.className="terminal-line "+kind;const stamp=new Date().toLocaleTimeString();el.innerHTML=`<span>${stamp}</span>${escapeHtml(message)}`;$("terminal").append(el);$("terminal").scrollTop=$("terminal").scrollHeight}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function api(url, options={}){const response=await fetch(url,{headers:{"Content-Type":"application/json",...(options.headers||{})},...options});let data={};try{data=await response.json()}catch{}if(!response.ok)throw new Error(data.error||`Request failed (${response.status})`);return data}
function showView(name){state.view=name;document.querySelectorAll(".view").forEach(v=>v.classList.toggle("active",v.id===`view-${name}`));document.querySelectorAll(".nav-item").forEach(b=>b.classList.toggle("active",b.dataset.target===name));$("crumbCurrent").textContent=navNames[name];if(name==="adb")refreshDevices();if(name==="diagnostics")runDiagnostics()}
document.querySelectorAll("[data-target]").forEach(b=>b.addEventListener("click",()=>showView(b.dataset.target)));
$("refreshAll").addEventListener("click",()=>{refreshHealth();if(state.view==="adb")refreshDevices();toast("Workspace refreshed")});
async function refreshHealth(){
 try{
  const h=await api("/api/health");$("systemStatus").textContent="BACKEND ONLINE";$("sideConnection").textContent="Backend online";$("sideSub").textContent="Render service responding";$("sideDot").classList.add("online");
  $("metricMeta").textContent=h.meta?.access_token_present&&h.meta?.package_id_present&&h.meta?.certificate_fingerprints_configured?"CONFIGURED":"SETUP NEEDED";
  $("metricMetaSub").textContent=h.meta?.access_token_present?"Meta credentials detected":"Add Meta credentials in Render";
  $("metaLine").style.width=h.meta?.access_token_present?"100%":"18%";
 }catch(e){$("systemStatus").textContent="BACKEND OFFLINE";$("sideConnection").textContent="Backend unavailable";$("sideSub").textContent=e.message;$("sideDot").classList.remove("online")}
 try{
  const a=await api("/api/adb/status");$("metricAdb").textContent=a.available?"BRIDGE ONLINE":"LOCAL AGENT";$("metricAdbSub").textContent=a.available?"ADB companion responding":"PC companion required";$("adbLine").style.width=a.available?"100%":"12%";
 }catch{$("metricAdb").textContent="NOT LINKED";$("metricAdbSub").textContent="Companion not reachable";$("adbLine").style.width="12%"}
}
async function getAgent(path,method="GET",body=null){
 const base=$("agentUrl").value.trim().replace(/\/+$/,"");if(!base)throw new Error("Enter the local ADB companion address.");
 const headers={"X-Agent-Token":$("agentToken")?.value||state.agentToken};
 const opts={method,headers};if(body){opts.body=JSON.stringify(body);headers["Content-Type"]="application/json"}
 const r=await fetch(base+path,opts);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.error||`Companion request failed (${r.status})`);return d;
}
$("saveAgent").addEventListener("click",async()=>{state.agentUrl=$("agentUrl").value.trim();state.agentToken=$("agentToken").value.trim();localStorage.setItem("adbAgentUrl",state.agentUrl);localStorage.setItem("adbAgentToken",state.agentToken);try{const d=await getAgent("/health");$("agentStatus").classList.add("online");$("agentStatus").innerHTML="<i></i> ONLINE";$("bridgeState").textContent="ONLINE";$("adbTag").textContent="BRIDGE ONLINE";log("ADB companion connected: "+(d.adb_path||"ADB executable not found"));toast("ADB companion reached")}catch(e){$("agentStatus").classList.remove("online");$("agentStatus").innerHTML="<i></i> OFFLINE";$("bridgeState").textContent="OFFLINE";$("adbTag").textContent="BRIDGE OFFLINE";log(e.message,"error");toast(e.message,true)}});
$("pairDevice").addEventListener("click",async()=>{const endpoint=$("pairEndpoint").value.trim(),code=$("pairCode").value.trim();if(!endpoint||!code){toast("Enter the pairing endpoint and six-digit code",true);return}try{const d=await getAgent("/api/pair","POST",{endpoint,pairing_code:code});log(d.output||"Pairing succeeded");$("pairCode").value="";toast("Pairing request completed");await refreshDevices()}catch(e){log(e.message,"error");toast(e.message,true)}});
$("connectDevice").addEventListener("click",async()=>{const endpoint=$("connectEndpoint").value.trim();if(!endpoint){toast("Enter the wireless debugging endpoint",true);return}try{const d=await getAgent("/api/connect","POST",{endpoint});log(d.output||"Connected");toast("ADB connect command completed");await refreshDevices()}catch(e){log(e.message,"error");toast(e.message,true)}});
async function refreshDevices(){
 try{const d=await getAgent("/api/devices");state.devices=d.devices||[];$("deviceEmpty").classList.toggle("hidden",state.devices.length>0);$("deviceList").innerHTML="";state.devices.forEach(dev=>{const b=document.createElement("button");b.className="device-card"+(state.selectedDevice===dev.serial?" selected":"");b.innerHTML=`<strong>${escapeHtml(dev.serial)}</strong><small>${escapeHtml(dev.state)} · ${escapeHtml(dev.details||"ADB device")}</small>`;b.addEventListener("click",()=>selectDevice(dev.serial));$("deviceList").append(b)});$("agentStatus").classList.add("online");$("agentStatus").innerHTML="<i></i> ONLINE";$("bridgeState").textContent="ONLINE";$("adbTag").textContent="BRIDGE ONLINE";$("metricAdb").textContent="BRIDGE ONLINE";$("metricAdbSub").textContent=`${d.count} device(s) visible`;log(`ADB inventory refreshed: ${d.count} device(s)`)}
 catch(e){$("deviceEmpty").classList.remove("hidden");$("deviceList").innerHTML="";$("agentStatus").classList.remove("online");$("agentStatus").innerHTML="<i></i> OFFLINE";$("bridgeState").textContent="OFFLINE";$("adbTag").textContent="BRIDGE OFFLINE";log(e.message,"warn")}
}
async function selectDevice(serial){state.selectedDevice=serial;document.querySelectorAll(".device-card").forEach(c=>c.classList.toggle("selected",c.querySelector("strong")?.textContent===serial));try{const d=await getAgent("/api/device-info","POST",{serial});const x=d.device;$("deviceInfo").classList.remove("hidden");$("deviceInfo").innerHTML=`<div class="surface-head"><div><span class="overline">SELECTED DEVICE</span><h3>${escapeHtml(x.model||serial)}</h3></div><span class="status-pill online"><i></i> CONNECTED</span></div><div class="info-grid">${[["MANUFACTURER",x.manufacturer],["ANDROID",x.android_release],["SDK",x.android_sdk],["BATTERY",x.battery_level==null?"—":x.battery_level+"%"],["SERIAL",x.serial],["BUILD",x.build_fingerprint]].map(([k,v])=>`<div class="info-cell"><span>${k}</span><b>${escapeHtml(v??"—")}</b></div>`).join("")}</div>`;log("Read basic device properties for "+serial)}catch(e){toast(e.message,true);log(e.message,"error")}}
$("refreshDevices").addEventListener("click",refreshDevices);
$("disconnectDevice").addEventListener("click",async()=>{const endpoint=$("connectEndpoint").value.trim();if(!endpoint){toast("Enter the device IP:port in the connect field to disconnect",true);return}try{const d=await getAgent("/api/disconnect","POST",{endpoint});log(d.output);toast("Device disconnected");state.selectedDevice=null;$("deviceInfo").classList.add("hidden");await refreshDevices()}catch(e){toast(e.message,true)}});
$("clearTerminal").addEventListener("click",()=>$("terminal").innerHTML="");
async function createChallenge(){
 const package_id=$("packageId").value.trim(),session_ref=$("sessionRef").value.trim();
 if(!package_id){toast("Enter your app's package ID",true);return}
 try{const d=await api("/api/challenge",{method:"POST",body:JSON.stringify({package_id,session_ref})});state.challenge=d;$("challengeCard").classList.remove("hidden");$("nonceValue").textContent=d.challenge_nonce;$("challengeMeta").textContent=`Package ${d.package_id} · ${d.nonce_length} characters · expires in ${d.expires_in}s`;$("challengeTimer").textContent=`${d.expires_in}S TTL`;toast("Fresh one-time challenge generated")}
 catch(e){toast(e.message,true)}
}
$("createChallenge").addEventListener("click",createChallenge);
$("copyNonce").addEventListener("click",()=>copyText(state.challenge?.challenge_nonce||""));
$("copyChallenge").addEventListener("click",()=>copyText(JSON.stringify(state.challenge,null,2)));
async function copyText(s){try{await navigator.clipboard.writeText(s);toast("Copied to clipboard")}catch{toast("Clipboard permission unavailable",true)}}
$("verifyMeta").addEventListener("click",async()=>{
 if(!state.challenge){toast("Generate a challenge first",true);return}
 const token=$("attestationToken").value.trim();if(!token){toast("Paste the token returned by your Quest app",true);return}
 const btn=$("verifyMeta");btn.disabled=true;btn.textContent="CONTACTING META…";
 try{
  const d=await api("/api/verify/meta",{method:"POST",body:JSON.stringify({challenge_id:state.challenge.challenge_id,challenge_nonce:state.challenge.challenge_nonce,attestation_token:token})});
  $("verifyResult").className="verify-result "+(d.ok?"good":"bad");$("verifyResult").textContent=d.ok?"Meta verified the token and all configured policy checks passed.":`Meta verified the signature, but local policy checks failed: ${(d.policy_issues||[]).join(", ")}`;
  $("claimsOutput").textContent=JSON.stringify(d,null,2);state.challenge=null;toast(d.ok?"Meta attestation verified":"Provider verified; policy rejected",!d.ok)
 }catch(e){$("verifyResult").className="verify-result bad";$("verifyResult").textContent=e.message;$("claimsOutput").textContent=JSON.stringify({error:e.message},null,2);toast(e.message,true)}
 finally{btn.disabled=false;btn.innerHTML='VERIFY TOKEN WITH META <b>↗</b>'}
});
$("copyClaims").addEventListener("click",()=>copyText($("claimsOutput").textContent));
async function runDiagnostics(){
 $("diagUpdated").textContent="RUNNING…";$("diagnosticRows").innerHTML="";
 const rows=[];
 try{const h=await api("/api/health");rows.push(["Flask backend","Online","ok","HTTP health endpoint responding"]);rows.push(["Meta App Access Token",h.meta.access_token_present?"Configured":"Missing",h.meta.access_token_present?"ok":"fail","Stored server-side in environment variables"]);rows.push(["Meta package ID",h.meta.package_id_present?"Configured":"Missing",h.meta.package_id_present?"ok":"fail","Expected application identifier"]);rows.push(["Certificate SHA-256",h.meta.certificate_fingerprints_configured+" fingerprint(s)",h.meta.certificate_fingerprints_configured?"ok":"fail","Expected signing certificate digest(s)"]);rows.push(["ADB companion",h.adb.agent_url_configured?"URL configured":"Not configured",h.adb.agent_url_configured?"ok":"warn",h.adb.note]);}
 catch(e){rows.push(["Flask backend","Offline","fail",e.message])}
 try{const a=await getAgent("/health");rows.push(["Local ADB companion",a.adb_found?"Online · adb found":"Online · adb missing",a.adb_found?"ok":"fail",a.adb_path||"Install Android Platform Tools on the PC"]);}catch(e){rows.push(["Local ADB companion","Not reachable","warn","Run adb_agent.py on the computer connected to the Quest. "+e.message])}
 $("diagnosticRows").innerHTML=rows.map(([name,value,status,detail])=>`<div class="diag-row"><span class="diag-icon">${status==="ok"?"✓":status==="fail"?"!":"·"}</span><div><b>${escapeHtml(name)} — ${escapeHtml(value)}</b><small>${escapeHtml(detail)}</small></div><span class="diag-state ${status==="ok"?"ok":status==="fail"?"fail":""}">${status.toUpperCase()}</span></div>`).join("");$("diagUpdated").textContent="UPDATED "+new Date().toLocaleTimeString();
}
$("runDiagnostics").addEventListener("click",runDiagnostics);
refreshHealth();

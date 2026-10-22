import {useEffect, useRef, useState} from 'react';

type Request = (path:string, method?:string, body?:unknown, key?:string)=>Promise<any>;
type Character = {id:string;name:string};
type Connection = {connected:boolean;character:Character|null;pending_turn_id:string|null;model_selection:string};
type Turn = {id:string;message:string;status:string;replies:Array<{id:string;name:string;text:string}>;observed_at:string|null;retry_after_seconds:number;error:string|null};
const pending = (t:Turn|null)=>!!t&&['prepared','queued','running'].includes(t.status);

export function PeopleWelcome({request}:{request:Request}){
  const [connection,setConnection]=useState<Connection|null>(null);
  const [token,setToken]=useState(''),[characters,setCharacters]=useState<Character[]>([]),[character,setCharacter]=useState('');
  const [turn,setTurn]=useState<Turn|null>(null),[history,setHistory]=useState<Turn[]>([]);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[renew,setRenew]=useState(false),[retry,setRetry]=useState(false);
  const [draft,setDraft]=useState('');
  // Memory only. The server retains pending intent across page reloads.
  const intent=useRef<{message:string;key:string}|null>(null);
  const mounted=useRef(true);
  useEffect(()=>{mounted.current=true;let active=true;
    request('/assistant/connection').then(async c=>{
      if(!active)return;setConnection(c);
      if(c.pending_turn_id){const t=await request('/assistant/messages/'+c.pending_turn_id);if(active)setTurn(t);}
    }).catch(e=>{if(active)setError(e.message);});
    return()=>{active=false;mounted.current=false;};
  },[request]);
  useEffect(()=>{
    if(!turn||!pending(turn)||turn.status==='prepared'||retry)return;
    let active=true;
    const timer=window.setTimeout(()=>{
      request('/assistant/messages/'+turn.id).then(t=>{if(active)setTurn(t);}).catch(e=>{if(active){setError(e.message);setRetry(true);}});
    },Math.max(2,turn.retry_after_seconds)*1000);
    return()=>{active=false;window.clearTimeout(timer);};
  },[turn,retry,request]);
  async function run(task:()=>Promise<void>){setBusy(true);setError('');try{await task();}catch(e){if(mounted.current)setError(e instanceof Error?e.message:'Support request failed');}finally{if(mounted.current)setBusy(false);}}
  async function recover(){
    const c=await request('/assistant/connection');if(!mounted.current)return;setConnection(c);
    if(c.pending_turn_id){const t=await request('/assistant/messages/'+c.pending_turn_id);if(mounted.current)setTurn(t);}
    else intent.current=null;
  }
  async function send(){
    const message=draft.trim();if(!message)return;
    intent.current??={message,key:crypto.randomUUID()};
    try{
      const t=await request('/assistant/messages','POST',{message:intent.current.message},intent.current.key);
      if(!mounted.current)return;
      if(turn&&!pending(turn))setHistory(h=>[...h,turn]);
      setTurn(t);setDraft('');intent.current=null;setRetry(false);
    }catch(e){await recover();setRetry(true);throw e;}
  }
  return <section className="panel padded chat">
    <div className="panel-title"><h2>✧ PeopleWelcome</h2><span className="state">READ-ONLY SUPPORT</span></div>
    <p className="muted">Ask about your instances and metered usage. Changes are confirmed in Nebula’s dashboard.</p>
    {error&&<p className="error" role="alert">{error}</p>}
    {connection?.connected&&<div className="support-connection"><span>Connected to <strong>{connection.character?.name}</strong></span><button className="secondary" onClick={()=>setRenew(v=>!v)}>Renew connection</button><button className="secondary" disabled={busy||pending(turn)} onClick={()=>void run(async()=>{await request('/assistant/connection','DELETE');setConnection(null);setToken('');await recover();})}>Disconnect</button></div>}
    {(!connection?.connected||renew)&&<form className="support-connect narrow" onSubmit={e=>{e.preventDefault();void run(async()=>{
      if(!characters.length){const out=await request('/assistant/connection','POST',{access_token:token});setCharacters(out.characters);setCharacter(out.characters[0]?.id||'');if(!out.characters.length)throw new Error('No active OpenAI characters found. Create or activate one in your PeopleWelcome account.');}
      else{const c=await request('/assistant/connection','POST',{access_token:token,ai_id:character});setConnection(c);setToken('');setCharacters([]);setRenew(false);setRetry(false);}
    });}}>
      <h3>{connection?.connected?'Renew PeopleWelcome access':'Connect your PeopleWelcome account'}</h3>
      <p>Use your authorized PeopleWelcome access token and an active character you own. Your token is encrypted on the server. An expired token can be renewed here with the same account.</p>
      <p className="fine">Your message, recent VM observations and prepaid usage summary will be shared with your connected character. Shared memory training stays off. Conversation history also appears in your PeopleWelcome account.</p>
      <label>PeopleWelcome access token<input type="password" value={token} onChange={e=>{setToken(e.target.value);setCharacters([]);}} autoComplete="off" spellCheck={false} required maxLength={16384}/></label>
      {characters.length>0&&<label>Support character<select value={character} onChange={e=>setCharacter(e.target.value)}>{characters.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}
      <button disabled={busy}>{busy?'Connecting…':characters.length?'Connect character':'Find my characters'}</button>
      <a href="https://peopl.ewelco.me/developer" target="_blank" rel="noreferrer">PeopleWelcome developer access ↗</a>
    </form>}
    <p className="fine">{connection?.model_selection||'PeopleWelcome selects its configured OpenAI model; documented default: gpt-6-luna.'}</p>
    <div className="messages" aria-live="polite">
      {[...history,...(turn?[turn]:[])].map(t=><div key={t.id}>
        <article className="message user"><strong>You</strong><p>{t.message}</p></article>
        <p className="fine">{t.status==='prepared'?'Submission needs resuming':t.status==='queued'?'Waiting for PeopleWelcome':t.status==='running'?'PeopleWelcome is replying':t.status==='failed'?'Reply failed':'Replies received'} · Cloud observations: {t.observed_at?new Date(t.observed_at).toLocaleString():'not collected'}</p>
        {t.replies.length>0&&<p className="fine">New replies from your connected PeopleWelcome conversation</p>}
        {t.replies.map(r=><article className="message assistant" key={r.id}><strong>{r.name}</strong><p>{r.text}</p></article>)}
        {t.error&&<p className="error">{t.error}</p>}
      </div>)}
      {!turn&&!history.length&&<div className="empty"><h3>How can I help with your cloud?</h3><p>Try “Show my instance statuses and cloud usage.”</p></div>}
    </div>
    {pending(turn)&&(turn?.status==='prepared'||retry)&&<button className="secondary" disabled={busy} onClick={()=>void run(async()=>{const t=await request('/assistant/messages/'+turn!.id+'/resume','POST');setTurn(t);setRetry(false);intent.current=null;setDraft('');})}>Resume existing request</button>}
    <form className="chat-input" onSubmit={e=>{e.preventDefault();void run(send);}}>
      <label className="sr-only" htmlFor="support-message">Message PeopleWelcome</label>
      <input id="support-message" value={draft} onChange={e=>{setDraft(e.target.value);if(!turn||!pending(turn))intent.current=null;}} placeholder="Ask PeopleWelcome…" maxLength={4000} required disabled={pending(turn)||busy}/>
      <button disabled={busy||!connection?.connected||pending(turn)}>{busy?'Sending…':'Send →'}</button>
    </form>
  </section>;
}

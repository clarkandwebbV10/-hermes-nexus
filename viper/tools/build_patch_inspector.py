#!/usr/bin/env python3
"""Build an offline, source-backed inspection view for this development patch.

Only Python's standard library and git are required. Generated verification
artifacts are excluded from the manifest to avoid circular hashes. Regenerate
after updating source files or the adjacent receipt.json.
"""

import argparse
import ast
import difflib
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "viper/docs/verification/2026-10-16/index.html"


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def collect_sources(baseline: str) -> list[dict]:
    changed = git("diff", "--name-only", "-z", baseline, "--", "viper")
    untracked = git("ls-files", "--others", "--exclude-standard", "-z", "--", "viper")
    paths = sorted(set((changed + untracked).decode().split("\0")) - {""})
    sources = []
    for name in paths:
        path = ROOT / name
        if name.startswith("viper/docs/verification/") or not path.is_file():
            continue
        if path.suffix not in {".py", ".json", ".toml", ".md", ".yml", ".yaml"}:
            continue
        raw = path.read_bytes()
        try:
            source = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        previous = subprocess.run(
            ["git", "show", f"{baseline}:{name}"], cwd=ROOT, capture_output=True, check=False
        )
        before = previous.stdout.decode("utf-8") if previous.returncode == 0 else ""
        sources.append({
            "path": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "baselineSha256": hashlib.sha256(previous.stdout).hexdigest() if previous.returncode == 0 else None,
            "source": source,
            "baselineSource": before,
            "diff": "".join(difflib.unified_diff(
                before.splitlines(keepends=True), source.splitlines(keepends=True),
                fromfile=f"{baseline[:7]}/{name}", tofile=f"working-tree/{name}"
            )),
        })
    return sources


def source_relationships(sources: list[dict]) -> list[dict]:
    paths = {source["path"] for source in sources}
    links = []
    for source in sources:
        if not source["path"].endswith(".py"):
            continue
        tree = ast.parse(source["source"])
        if any(isinstance(node, ast.Import) and any(alias.name == "viper" for alias in node.names)
               for node in ast.walk(tree)):
            links.append({"from": source["path"], "to": "viper/viper.py", "label": "imports runtime"})
    for origin, target, label in (
        ("viper/pyproject.toml", "viper/viper.py", "declares CLI entry points"),
        ("viper/claim.schema.json", "viper/viper.py", "describes shared boolean contract"),
        ("viper/README.md", "viper/viper.py", "documents runtime behavior"),
        ("viper/tools/check_package.py", "viper/pyproject.toml", "reads package metadata"),
    ):
        if origin in paths and target in paths:
            links.append({"from": origin, "to": target, "label": label})
    return links


PAGE = r'''<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hidden Viper · Boolean validation patch</title>
<style>
:root{color-scheme:dark;font:15px/1.5 system-ui,sans-serif;color:#ecf4ff;background:#091526;--blue:#52beff;--gold:#ffce42;--red:#ff655c;--line:#436381}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 65% 0,#164a78,transparent 60%),#091526}button,a{font:inherit}button{cursor:pointer;color:inherit;background:#142c45;border:1px solid var(--line);border-radius:9px;padding:8px 12px}button:hover,button:focus-visible,a:focus-visible{outline:2px solid var(--blue);outline-offset:3px}button[aria-pressed=true]{border-color:var(--gold);background:#284465}a{color:var(--blue)}header,main{max-width:1460px;margin:auto;padding:24px}header{padding-bottom:0}.eyebrow{color:var(--gold);letter-spacing:.13em;font-size:.8rem}h1{font-size:clamp(1.8rem,4vw,3rem);line-height:1.15;margin:10px 0}h2{font-size:1.1rem;margin:0 0 12px}h3{font-size:1rem;margin:18px 0 8px}p{margin:8px 0}.muted{color:#b7c9dc}.facts{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.fact{border:1px solid var(--line);border-radius:12px;padding:10px 15px;background:#10283eda}.fact strong{color:var(--gold)}.layout{display:grid;grid-template-columns:minmax(340px,1fr) minmax(360px,1.15fr);gap:18px}.panel{min-width:0;background:#0d2135e8;border:1px solid var(--line);border-radius:16px;padding:18px}.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}.toolbar small{margin-right:auto}.stage{position:relative;overflow:hidden;height:355px;perspective:1100px;border-radius:12px;background:radial-gradient(ellipse,#1b4b6e,#071322);border:1px solid #315777;touch-action:none}.world{position:absolute;left:50%;top:50%;width:0;height:0;transform-style:preserve-3d;transform:rotateX(var(--rx,12deg)) rotateY(var(--ry,-15deg))}.node{position:absolute;width:155px;min-height:86px;padding:10px;text-align:left;overflow-wrap:anywhere;transform:translate3d(var(--x),var(--y),var(--z));border:1px solid var(--blue);box-shadow:0 10px 24px #0008,inset 0 1px #dceaff66;background:linear-gradient(145deg,#254d71,#102940)}.node b{display:block;font-size:.8rem}.node small{display:block;color:#c8d9e8;font-size:.67rem;margin-top:6px}.node[aria-pressed=true]{border-color:var(--gold);box-shadow:0 0 22px #ffce4255}.node.test{border-left:4px solid var(--gold)}.node.tool{border-left:4px solid var(--red)}.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.8rem;margin:10px 0;color:#c8d9e8}.legend span:before{content:'●';color:var(--blue);margin-right:5px}.legend .test:before{color:var(--gold)}.legend .tool:before{color:var(--red)}.file-list{display:grid;gap:7px;margin-top:14px}.file-list button{text-align:left;font-size:.82rem;display:flex;justify-content:space-between;gap:8px}.file-list small{white-space:nowrap;color:#b7c9dc}.code{font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre;overflow:auto;max-height:650px;margin:14px 0 0;padding:15px;background:#060f1b;border:1px solid #284764;border-radius:10px;tab-size:4}.hash{font:11px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}.selected-path{overflow-wrap:anywhere;color:var(--blue)}.detail-meta{display:grid;gap:6px}.relationship{font-size:.82rem;border-top:1px solid #294762;padding:8px 0;overflow-wrap:anywhere}.receipt{margin-top:18px}.result{padding:12px 0;border-top:1px solid #294762;display:grid;gap:4px}.badge{font-size:.75rem;border:1px solid var(--line);border-radius:5px;padding:2px 6px;display:inline-block}.expected{color:var(--gold);border-color:#977923}.unexpected{color:var(--red);border-color:var(--red)}details{margin-top:12px}summary{cursor:pointer;color:var(--blue)}footer{margin:20px 0 0;color:#b7c9dc;font-size:.8rem}body.flat .stage,body.flat .rotation{display:none}
@media(max-width:950px){.layout{grid-template-columns:1fr}.code{max-height:480px}}@media(max-width:540px){header,main{padding:16px}.panel{padding:13px}.stage{height:315px;perspective:950px}.node{width:116px;min-height:95px;padding:7px}.node b{font-size:.68rem}.node small{font-size:.58rem}.fact{font-size:.82rem;padding:8px 10px}.file-list button{font-size:.74rem}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>
<header><div class="eyebrow">HIDDEN VIPER / DEVELOPMENT INSPECTION / 16 OCT 2026</div>
<h1>Claims need typed expectations.</h1>
<p class="muted">Inspect the boolean validation correction, its source relationships, and executable verification evidence.</p>
<div class="facts"><div class="fact">Baseline <strong id="baseline"></strong></div><div class="fact">Source version <strong id="version"></strong></div><div class="fact"><strong id="count"></strong> changed text files</div><div class="fact">Development patch · release not published</div></div></header>
<main><div class="layout"><section class="panel"><h2>Spatial source map</h2><p class="muted">Each tile is a real changed file. Select a tile or use the accessible file list below.</p>
<div class="toolbar"><small>Drag empty space to rotate.</small><button id="flat" type="button" aria-pressed="false">Flat view</button><button class="rotation" id="left" aria-label="Rotate map left">←</button><button class="rotation" id="right" aria-label="Rotate map right">→</button><button class="rotation" id="reset">Reset</button></div>
<div class="stage" id="stage" aria-label="Three-dimensional source map"><div class="world" id="world"></div></div>
<div class="legend"><span>Source / metadata</span><span class="test">Tests</span><span class="tool">Tools</span></div>
<nav class="file-list" id="files" aria-label="Changed source files"></nav>
<details><summary>Source relationships</summary><div id="relationships"></div><p class="muted">Labels distinguish imports, metadata, and shared contracts. This map represents source structure.</p></details></section>
<section class="panel" aria-label="Source drilldown"><h2 class="selected-path" id="selected">Select a source file</h2><div class="detail-meta" id="meta"></div>
<div class="toolbar" role="group" aria-label="Source representation"><button data-mode="source" aria-pressed="true">Current source</button><button data-mode="diff" aria-pressed="false">Patch diff</button><button data-mode="baselineSource" aria-pressed="false">Baseline source</button></div>
<pre class="code" id="source" tabindex="0" aria-label="Selected source text"></pre></section></div>
<section class="panel receipt"><h2>Execution receipt</h2><p id="receipt-state"></p><div id="results"></div><details><summary>Embedded receipt JSON</summary><pre class="code" id="receipt-json" tabindex="0"></pre></details></section>
<footer id="footer"></footer></main>
<script id="patch-data" type="application/json">__PATCH_DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('patch-data').textContent), $=id=>document.getElementById(id);
const make=(tag,text,className)=>{const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;return el};
$('baseline').textContent=data.baselineCommit.slice(0,7);$('baseline').title=data.baselineCommit;$('version').textContent=data.version;$('count').textContent=data.sources.length;
let selected=0,mode='source',rx=12,ry=-15;
function render(){const source=data.sources[selected];if(!source)return;$('selected').textContent=source.path;$('meta').replaceChildren(make('div',source.bytes+' bytes · '+(source.baselineSha256?'modified':'added'),'muted'),make('div','SHA256 '+source.sha256,'hash'),make('div','Baseline SHA256 '+(source.baselineSha256||'new file'),'hash'));$('source').textContent=source[mode]||(mode==='baselineSource'?'File absent from baseline.':'No content.');document.querySelectorAll('[data-file]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.file)===selected)));document.querySelectorAll('[data-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)));}
data.sources.forEach((source,index)=>{const group=source.path.includes('/tests/')?'test':source.path.includes('/tools/')?'tool':'';const node=make('button','',`node ${group}`);node.type='button';node.dataset.file=index;node.append(make('b',source.path.replace('viper/','')),make('small',source.sha256.slice(0,12)+'…'));const mobile=matchMedia('(max-width:540px)').matches,w=mobile?124:166;const columns=mobile?3:4;node.style.setProperty('--x',((index%columns-(columns-1)/2)*w- (mobile?58:77))+'px');node.style.setProperty('--y',(Math.floor(index/columns)*101-130)+'px');node.style.setProperty('--z',(Math.floor(index/columns)%2*35)+'px');const row=make('button','');row.type='button';row.dataset.file=index;row.append(make('span',source.path),make('small',source.baselineSha256?'modified':'added'));for(const button of [node,row])button.addEventListener('click',()=>{selected=index;render()});$('world').append(node);$('files').append(row)});
for(const link of data.relationships){const row=make('div','', 'relationship'),from=make('button',link.from.replace('viper/','')),to=make('button',link.to.replace('viper/',''));from.type=to.type='button';for(const [button,path]of[[from,link.from],[to,link.to]])button.addEventListener('click',()=>{const index=data.sources.findIndex(source=>source.path===path);if(index>=0){selected=index;render()}});row.append(from,document.createTextNode(' → '+link.label+' → '),to);$('relationships').append(row)}
document.querySelectorAll('[data-mode]').forEach(button=>button.addEventListener('click',()=>{mode=button.dataset.mode;render()}));
function rotate(){ $('world').style.setProperty('--rx',rx+'deg');$('world').style.setProperty('--ry',ry+'deg') }$('left').onclick=()=>{ry-=12;rotate()};$('right').onclick=()=>{ry+=12;rotate()};$('reset').onclick=()=>{rx=12;ry=-15;rotate()};$('flat').onclick=()=>{const flat=document.body.classList.toggle('flat');$('flat').setAttribute('aria-pressed',String(flat));$('flat').textContent=flat?'Show 3D view':'Flat view'};
let drag=null;$('stage').addEventListener('pointerdown',event=>{if(event.target.closest('button'))return;drag={x:event.clientX,y:event.clientY,rx,ry};$('stage').setPointerCapture(event.pointerId)});$('stage').addEventListener('pointermove',event=>{if(!drag)return;ry=drag.ry+(event.clientX-drag.x)*.2;rx=Math.max(-30,Math.min(35,drag.rx-(event.clientY-drag.y)*.2));rotate()});for(const event of ['pointerup','pointercancel'])$('stage').addEventListener(event,()=>{drag=null});
if(data.receipt){const results=Array.isArray(data.receipt.results)?data.receipt.results:[],matches=results.filter(result=>result.returncode===result.expectedReturncode).length;$('receipt-state').textContent=results.length?`${matches}/${results.length} commands returned their recorded expected exit code. Expected failures are identified by their exit codes.`:'Receipt present; no execution results recorded.';for(const result of results){const row=make('div','', 'result');row.append(make('strong',result.name||'Unnamed command'),make('span',`exit ${result.returncode} · expected ${result.expectedReturncode}`,`badge ${result.returncode===result.expectedReturncode?'expected':'unexpected'}`));if(result.outputLog){const log=String(result.outputLog),link=make('a','Open recorded output: '+log);if(!/^[a-z][a-z0-9+.-]*:/i.test(log)&&!log.startsWith('//'))link.href=log;row.append(link)}$('results').append(row)}const hashes=data.receipt.sourceSha256||{},recorded=data.sources.filter(source=>Object.hasOwn(hashes,source.path)),matched=recorded.filter(source=>hashes[source.path]===source.sha256).length;$('receipt-state').append(document.createTextNode(` Source hashes: ${matched}/${recorded.length} recorded files match this embedded view; ${data.sources.length-recorded.length} displayed files have no receipt hash.`));$('receipt-json').textContent=JSON.stringify(data.receipt,null,2)}else{$('receipt-state').textContent='Awaiting receipt.json. No executable verification results are embedded in this view.';$('receipt-json').textContent='null'}
$('footer').textContent='Offline snapshot · baseline '+data.baselineCommit+' · Source text and receipt are embedded. Regenerate after changes. The spatial map does not represent running agents or formal verification.';render();
</script>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="b186ce7")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    baseline = git("rev-parse", "--verify", f"{args.baseline}^{{commit}}").decode().strip()
    sources = collect_sources(baseline)
    runtime = ast.parse((ROOT / "viper/viper.py").read_text(encoding="utf-8"))
    version = next(node.value.value for node in runtime.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "VERSION" for target in node.targets))
    receipt_path = args.output.parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
    payload = {"baselineCommit": baseline, "version": version, "sources": sources,
               "relationships": source_relationships(sources), "receipt": receipt}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(PAGE.replace("__PATCH_DATA__", encoded), encoding="utf-8")
    print(f"Built {args.output}: {len(sources)} source files; receipt {'embedded' if receipt is not None else 'awaiting'}.")


if __name__ == "__main__":
    main()

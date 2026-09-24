"use strict";
// Application wiring in a lightweight DOM double. This is not visual/browser QA.
const test=require("node:test"),assert=require("node:assert/strict"),vm=require("node:vm"),fs=require("node:fs"),path=require("node:path");
class Element {
  constructor(tag="div"){this.tagName=tag;this.children=[];this.textContent="";this.attributes={};this.dataset={};this.style={};this.events={};this.value="";this.hidden=false;this.classList={toggle(){}};}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=[...nodes];this.textContent="";}
  setAttribute(name,value){this.attributes[name]=value;}
  addEventListener(name,handler){this.events[name]=handler;}
  scrollIntoView(){}
  requestSubmit(){this.events.submit?.({preventDefault(){}});}
  get text(){return this.textContent+this.children.map(x=>x.text??x.textContent??"").join(" ");}
}
async function page(htmlFile,scriptFile,lang="zh"){
  const root=path.join(__dirname,".."),html=fs.readFileSync(path.join(root,"web",htmlFile),"utf8"),elements={};
  for(const match of html.matchAll(/<[^>]*\bid="([^"]+)"[^>]*>/g)){const e=elements[match[1]]=new Element();e.value=match[0].match(/\bvalue="([^"]*)"/)?.[1]||"";}
  const created=[];const document={getElementById:id=>elements[id]||null,createElement:tag=>{const e=new Element(tag);created.push(e);return e;},querySelectorAll:selector=>selector===".segment"?created.filter(e=>e.className?.split(" ").includes("segment")):[]};
  const fixture={components:[{id:"idf/nvs_flash",version:"fixture",status:"ok",maintainer:"espressif",definitions:2,unresolved:0,url:"https://example.com/nvs",diagnostics:0}],overlaps:[],definitions:[
    {symbol:"ESP_ERR_NVS_BASE",value:0x1100,hex:"0x1100",role:"base",expression:"0x1100",component:"idf/nvs_flash",version:"fixture",conditions:[],base_symbols:[],resolution:"resolved",file:"nvs.h",line:1,source_url:"https://example.com/nvs",configurable:false},
    {symbol:"ESP_ERR_NVS_NOT_INITIALIZED",value:0x1101,hex:"0x1101",role:"error",expression:"ESP_ERR_NVS_BASE + 1",component:"idf/nvs_flash",version:"fixture",conditions:[],base_symbols:["ESP_ERR_NVS_BASE"],resolution:"resolved",file:"nvs.h",line:2,source_url:"https://example.com/nvs",configurable:false}
  ]};
  document.documentElement={dataset:{}};
  const {translate}=require("../web/i18n.js");
  const errors=[];const context={I18n:{lang,t:(text,...args)=>translate(text,args,lang)},document,URL,location:{href:"https://example.com/index/",origin:"https://example.com"},window:{innerWidth:1200},console:{error:e=>errors.push(e)},fetch:async()=>({ok:true,json:async()=>fixture})};
  vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(root,"web/space.js"),"utf8"),context);
  vm.runInContext(fs.readFileSync(path.join(root,"web",scriptFile),"utf8"),context);
  await new Promise(resolve=>setImmediate(resolve));assert.equal(errors.length,0,String(errors));return elements;
}
test("home loads data, filters segments and checks ranges",async()=>{
  const e=await page("index.html","app.js");assert.ok(e["space-map"].children.length>0);
  e["map-query"].value="0x1101";e["map-query"].events.input();assert.equal(e["space-map"].children.length,1);assert.match(e["detail-body"].text,/nvs_flash/);
  e["range-base"].value="0x1100";e["range-count"].value="256";e["range-form"].requestSubmit();assert.match(e["range-result"].text,/发现.*已定义/);
  e["range-base"].value="0x7000";e["range-form"].requestSubmit();assert.match(e["range-result"].text,/未发现.*重叠/);assert.match(e["range-result"].text,/不是可用性保证/);
  e["map-query"].value="unknown-component-name";e["map-query"].events.input();assert.match(e["detail-heading"].textContent,/没有匹配/);
});
test("diagnostic entry retains the detailed definition table",async()=>{
  const e=await page("diagnostics.html","diagnostics.js");assert.ok(e.components.children.length>0);assert.ok(e.definitions.children.length>0);
  e.query.value="0x1101";e.query.events.input();assert.equal(e.definitions.children.length,1);assert.match(e.definitions.text,/ESP_ERR_NVS_NOT_INITIALIZED/);
});
test("English renders dynamic results, validation and diagnostic filters",async()=>{
  const e=await page("index.html","app.js","en");
  assert.match(e.status.text,/Selected versions of 1 components/);
  e["range-base"].value="0x1100";e["range-count"].value="256";e["range-form"].requestSubmit();
  assert.match(e["range-result"].text,/Found 2 defined values/);
  e["range-base"].value="0x7000";e["range-form"].requestSubmit();assert.match(e["range-result"].text,/No overlap/);
  e["range-base"].value="invalid";e["range-form"].requestSubmit();assert.match(e["range-result"].text,/Enter a BASE/);
  e["map-query"].value="missing";e["map-query"].events.input();assert.equal(e["detail-heading"].textContent,"No matching ranges");
  const d=await page("diagnostics.html","diagnostics.js","en");assert.match(d.count.text,/2 matches/);assert.match(d.components.text,/Scanned/);
  assert.doesNotMatch(Object.values(e).map(x=>x.text).join(""),/[\u4e00-\u9fff]/);
  assert.doesNotMatch(Object.values(d).map(x=>x.text).join(""),/[\u4e00-\u9fff]/);
});

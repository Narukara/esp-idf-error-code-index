"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const {en,translate,localizePage,selectLanguage}=require("../web/i18n.js");
const source=name=>fs.readFileSync(path.join(__dirname,"../web",name),"utf8");
test("all static UI text and translation calls have English entries",()=>{
  const keys=[];
  for(const name of ["index.html","diagnostics.html"]){
    const html=source(name);
    for(const m of html.matchAll(/>([^<>]+)</g))if(/[\u4e00-\u9fff]/.test(m[1])&&m[1].trim()!=="中文")keys.push(m[1].trim());
    for(const m of html.matchAll(/(?:aria-label|placeholder)="([^"]+)"/g))if(/[\u4e00-\u9fff]/.test(m[1])&&!m[1].includes("Language /"))keys.push(m[1]);
  }
  for(const name of ["app.js","diagnostics.js"])for(const m of source(name).matchAll(/\btr\("([^"]+)"/g))keys.push(m[1].trim());
  for(const key of keys)assert.ok(Object.hasOwn(en,key),`Missing translation: ${key}`);
});
test("translation keeps source evidence literal and substitutes without HTML",()=>{
  assert.equal(translate("发现 {0} 个已定义数值或标记",[2],"en"),"Found 2 defined values or markers");
  assert.equal(translate("发现 {0} 个已定义数值或标记",[2],"zh"),"发现 2 个已定义数值或标记");
  assert.equal(translate("ESP_ERR_WIFI_BASE",[],"en"),"ESP_ERR_WIFI_BASE");
  assert.equal(translate("{0} 个数值",["<b>"],"en"),"<b> values");
});
function boot(query,saved,browser="en-US",blocked=false){
  const nodes=[{nodeValue:"Error code space",parentElement:{tagName:"H1"}}];let offset=0,handler,assigned,written;
  const select={addEventListener:(_,fn)=>handler=fn};
  const document={title:"ESP-IDF Error Code Space",documentElement:{},body:{},createTreeWalker:()=>({nextNode:()=>nodes[offset++]}),querySelectorAll:()=>[],getElementById:()=>select};
  const context={document,URL,NodeFilter:{SHOW_TEXT:4},navigator:{language:browser},location:{href:"https://example.org/index/diagnostics.html"+query,assign:url=>assigned=url},localStorage:{getItem:()=>{if(blocked)throw Error();return saved;},setItem:(_,value)=>{if(blocked)throw Error();written=value;}}};
  vm.createContext(context);vm.runInContext(source("i18n.js"),context);
  return {context,nodes,switchTo(value){select.value=value;handler();return {assigned,written};}};
}
test("language selection uses URL, saved preference, then browser language",()=>{
  assert.equal(boot("?lang=en","zh").context.I18n.lang,"en");
  assert.equal(boot("","zh").context.I18n.lang,"zh");
  assert.equal(boot("",null,"zh-TW").context.I18n.lang,"zh");
  assert.equal(boot("?lang=invalid",null,"fr").context.I18n.lang,"en");
  const page=boot("?lang=en",null);assert.equal(page.nodes[0].nodeValue,"Error code space");assert.equal(page.context.document.documentElement.lang,"en");
  const changed=page.switchTo("zh");assert.equal(changed.written,"zh");assert.equal(changed.assigned,"https://example.org/index/diagnostics.html?lang=zh");
  assert.match(boot("?lang=en",null,"en",true).switchTo("zh").assigned,/lang=zh/);
});
test("browser preference order and English fallback",()=>{
  assert.equal(selectLanguage(null,null,["en-GB","zh-CN"]),"en");
  assert.equal(selectLanguage(null,null,["zh-TW","en-US"]),"zh");
  assert.equal(selectLanguage(null,null,["fr-FR","zh-Hans"]),"zh");
  assert.equal(selectLanguage(null,null,["fr-FR"]),"en");
  assert.equal(selectLanguage(null,null,[]),"en");
  assert.equal(selectLanguage(null,"en",["zh-CN"]),"en");
  assert.equal(selectLanguage("zh","en",["en-US"]),"zh");
  assert.equal(selectLanguage(null,"invalid",[undefined,"EN-us"]),"en");
});
test("static pages default to English and can localize back to Chinese",()=>{
  for(const name of ["index.html","diagnostics.html"]){
    const html=source(name);
    assert.match(html,/<html lang="en">/);
    assert.match(html,/<option value="en" selected>English<\/option>/);
    assert.doesNotMatch(html.replaceAll("中文","").replaceAll("语言",""),/[\u4e00-\u9fff]/);
    for(const m of html.matchAll(/>([^<>]+)</g)){
      const value=m[1].trim();
      if(Object.values(en).includes(value))assert.match(localizePage(value,"zh"),/[\u4e00-\u9fff]/);
    }
  }
  const page=boot("?lang=zh",null);
  assert.equal(page.nodes[0].nodeValue,"错误码空间");
  assert.equal(page.context.document.title,"ESP-IDF 错误码空间");
});

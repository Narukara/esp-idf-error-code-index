"use strict";
const test=require("node:test"), assert=require("node:assert/strict"), S=require("../web/space.js");
const record=(value,more={})=>({value,role:"error",component:"vendor/test",symbol:"ERR_"+value,expression:String(value),file:"x.h",source_url:"https://example.com/x",...more});
test("entire signed space is covered without per-value allocation",()=>{
  const rows=S.segments([record(0,{role:"shared"}),record(0x1101)]);
  assert.equal(rows[0].start,S.MIN);assert.equal(rows.at(-1).end,S.MAX);
  assert.equal(rows.reduce((n,r)=>n+r.end-r.start+1,0),4294967296);
  for(let i=1;i<rows.length;i++)assert.equal(rows[i-1].end+1,rows[i].start);
  assert.ok(rows.length<=5);
});
test("sparse definitions do not fill holes or reserve a BASE block",()=>{
  const rows=S.segments([record(0x7000,{role:"base"}),record(0x7001),record(0x7010)],0x7000,0x7100);
  assert.equal(rows.find(r=>r.start===0x7002).end,0x700f);
  assert.equal(rows.find(r=>r.start===0x7002).state,"unobserved");
  assert.equal(rows[0].state,"base");
});
test("contiguous same-component definitions merge, component changes split",()=>{
  const rows=S.segments([record(1),record(2),record(3,{component:"other/x"})],1,3);
  assert.equal(rows.length,2);assert.equal(rows[0].end,2);
});
test("duplicate and alias are distinct from independent overlaps",()=>{
  assert.equal(S.segments([record(1),record(1)],1,1)[0].state,"occupied");
  assert.equal(S.segments([record(1),record(1,{alias_of:"ERR_1",symbol:"OLD"})],1,1)[0].state,"occupied");
  assert.equal(S.segments([record(1),record(1,{symbol:"OTHER",component:"other/x"})],1,1)[0].state,"overlap");
});
test("unresolved and excluded definitions are not painted",()=>{
  assert.equal(S.segments([record(null),record(2,{role:"excluded"})],0,10)[0].state,"unobserved");
});
test("range checking includes markers and validates inclusive endpoints",()=>{
  const result=S.checkRange([record(0x7000,{role:"base"}),record(0x70ff),record(0x7100)],"0x7000","256");
  assert.equal(result.matches.length,2);assert.equal(result.end,0x70ff);
  assert.ok(S.checkRange([],"0x7fffffff","2").error);
  assert.ok(S.checkRange([],"0x7000","0").error);
  assert.ok(S.checkRange([],"3.5","2").error);
  assert.equal(S.checkRange([],"-0x80000000","4294967296").end,S.MAX);
});
test("compressed heights vary but giant gaps remain bounded",()=>{
  assert.ok(S.height({start:0,end:1})<S.height({start:0,end:1000}));
  assert.ok(S.height({start:S.MIN,end:S.MAX})<=158);
  assert.equal(S.parseNumber("-0x1"),-1);assert.equal(S.parseNumber("0XFFFF"),65535);
});

import asyncio
import json
import pytest
from app.store import Store
from app.orchestrator import Orchestrator
from app.local_runner import command_spec, run_local, test_count as count_tests
from app.security import safe_path


def final(status="completed"):
    return {"status":status,"summary":"Fixture verified","findings":[],"changes":[],"test_suite":"none"}


def step(action, *, path="", query="", command="none", changes=None, result=None):
    return {"action":action,"path":path,"query":query,"command":command,"changes":changes or [],"result":result}


def test_real_local_test_runner_and_zero_tests(tmp_path):
    async def scenario():
        (tmp_path/'tests').mkdir()
        (tmp_path/'tests/test_value.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_value(self): self.assertEqual(2+2,4)\n')
        output=await run_local(tmp_path,'test',30)
        assert output['executed'] and output['test_count']==1 and output['exit_code']==0
        (tmp_path/'tests/test_value.py').write_text('')
        empty=await run_local(tmp_path,'test',30)
        assert empty['exit_code']!=0 and empty['test_count']==0
    asyncio.run(scenario())


def test_auto_workflow_reads_writes_executes_and_repairs(tmp_path):
    async def scenario():
        root=tmp_path/'workspaces'/'p';root.mkdir(parents=True)
        (root/'tests').mkdir()
        (root/'tests/test_calc.py').write_text('import unittest\nfrom calc import add\nclass T(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n')
        store=Store(tmp_path/'db.sqlite')
        store.save('projects',{'id':'p','workspace':str(root),'requirement':'Add function'},'project.created')
        class ScriptedProvider:
            count=0
            failure_seen=False
            async def generate(self,instructions,prompt,schema,emit,**settings):
                context=json.loads(prompt)
                role=context['task']['agent_id']
                if role=='frontend':
                    seq=[step('list'),step('write',changes=[{'path':'calc.py','content':'def add(a,b): return a-b\n'}]),step('command',path='.',command='test'),step('read',path='calc.py'),step('write',changes=[{'path':'calc.py','content':'def add(a,b): return a+b\n'}]),step('command',path='.',command='test'),step('finish',result=final())]
                    item=seq[self.count];self.count+=1
                    if self.count==4:
                        self.failure_seen=any(h.get('output',{}).get('exit_code')==1 for h in context['tool_history'])
                    return item
                if role=='qa':
                    if not context['tool_history']:return step('command',path='.',command='test')
                    return step('finish',result=final())
                return step('finish',result=final())
        provider=ScriptedProvider();o=Orchestrator(store,provider)
        for i,role in enumerate(['frontend','qa','reviewer']):
            store.save('tasks',{'id':str(i),'project_id':'p','agent_id':role,'title':role,'description':'Fixture task','status':'pending','attempts':0,'depends_on':[str(i-1)] if i else [],'acceptance_criteria':[]},'task.created')
        o.start_workflow('p',auto_approve=True)
        await o.pipeline
        assert all(t['status']=='completed' for t in store.all('tasks'))
        assert provider.failure_seen
        assert 'return a+b' in (root/'calc.py').read_text()
        assert not o.waiters and not o.workflow_auto
        assert any(e['type']=='approval.auto_authorized' for e in store.recent())
        assert store.get('tasks','1')['result']['test_result']['test_count']==1
        store.engine.dispose()
    asyncio.run(scenario())


def test_unknown_commands_and_protected_paths(tmp_path):
    for command in ['docker','deploy','delete','shell','dev']:
        with pytest.raises(ValueError):command_spec(tmp_path,command)
    with pytest.raises(ValueError):safe_path(tmp_path,'../outside.py')
    with pytest.raises(ValueError):safe_path(tmp_path,'.office-runtime/empty-npmrc')
    assert count_tests('Tests  12 passed (12)')==12


def test_qa_cannot_finish_without_real_tests(tmp_path):
    from app.workspace_agent import WorkspaceAgent
    from app.orchestrator import Result
    async def scenario():
        class Provider:
            calls=0
            async def generate(self,*args,**kwargs):
                self.calls+=1
                return step('finish',result=final('completed' if self.calls==1 else 'blocked'))
        async def yes(*args):return True
        provider=Provider();engine=WorkspaceAgent(tmp_path,'qa',provider,yes,lambda *a,**k:None,{}, {})
        out=await engine.run('QA',{},Result)
        assert out['status']=='blocked' and provider.calls==2
    asyncio.run(scenario())


def test_cancel_stops_local_process(tmp_path):
    async def scenario():
        (tmp_path/'tests').mkdir()
        (tmp_path/'tests/test_slow.py').write_text('import unittest,time\nclass T(unittest.TestCase):\n def test_slow(self): time.sleep(30)\n')
        with pytest.raises(TimeoutError):await run_local(tmp_path,'test',1)
    asyncio.run(scenario())

def test_real_npm_build_and_test_commands(tmp_path):
    import shutil
    if not shutil.which('node') or not shutil.which('npm'): pytest.skip('Node runtime unavailable')
    async def scenario():
        (tmp_path/'package.json').write_text(json.dumps({'name':'isolated-workflow-test','version':'1.0.0','scripts':{'build':'node --check calc.cjs','test':'node --test'}}))
        (tmp_path/'calc.cjs').write_text('module.exports = (a,b) => a+b;\n')
        (tmp_path/'calc.test.cjs').write_text("const test=require('node:test');const assert=require('node:assert/strict');test('adds',()=>assert.equal(require('./calc.cjs')(2,3),5));\n")
        build=await run_local(tmp_path,'build',30)
        tests=await run_local(tmp_path,'test',30)
        assert build['exit_code']==0, build['output']
        assert tests['exit_code']==0 and tests['test_count']==1, tests['output']
        install=command_spec(tmp_path,'install')
        assert '--ignore-scripts' in install
    asyncio.run(scenario())

def test_tool_write_permissions_and_approval_hash(tmp_path):
    from app.workspace_agent import WorkspaceAgent
    async def scenario():
        target=tmp_path/'value.py';target.write_text('OLD=1\n')
        async def changed_during_approval(*args):
            target.write_text('HUMAN_EDIT=1\n')
            return True
        engine=WorkspaceAgent(tmp_path,'frontend',None,changed_during_approval,lambda *a,**k:None,{}, {'value.py':'OLD=1\n'})
        with pytest.raises(ValueError,match='changed after approval'):
            await engine.write([{'path':'value.py','content':'NEW=1\n'}])
        assert target.read_text()=='HUMAN_EDIT=1\n'
        for role,path in [('planner','x.py'),('reviewer','x.py'),('qa','src/main.ts'),('devops','Dockerfile')]:
            restricted=WorkspaceAgent(tmp_path,role,None,changed_during_approval,lambda *a,**k:None,{}, {})
            with pytest.raises(ValueError):await restricted.write([{'path':path,'content':'invalid'}])
    asyncio.run(scenario())


def test_auto_retry_budget_stops_at_three(tmp_path):
    async def scenario():
        root=tmp_path/'workspaces'/'p';root.mkdir(parents=True)
        store=Store(tmp_path/'db.sqlite')
        store.save('projects',{'id':'p','workspace':str(root),'requirement':'Fixture'},'project.created')
        class BrokenProvider:
            calls=0
            async def generate(self,*args,**kwargs):
                self.calls+=1
                raise RuntimeError('Fixture provider failure')
        provider=BrokenProvider();o=Orchestrator(store,provider)
        store.save('tasks',{'id':'t','project_id':'p','agent_id':'frontend','title':'fixture','description':'fixture','status':'pending','attempts':0,'depends_on':[],'acceptance_criteria':[]},'task.created')
        o.start_workflow('p',auto_approve=True);await o.pipeline
        assert provider.calls==3 and store.get('tasks','t')['attempts']==3
        assert store.get('tasks','t')['status']=='failed' and not o.active and not o.workflow_auto
        store.engine.dispose()
    asyncio.run(scenario())

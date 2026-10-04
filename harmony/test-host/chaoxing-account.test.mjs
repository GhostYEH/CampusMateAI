import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { stripTypeScriptTypes } from 'node:module';
import test from 'node:test';
import { runInNewContext } from 'node:vm';

// Execute the real request/parser/repository code with an SDK transport stub.
function load(relative, dependencies = {}) {
  const source = readFileSync(new URL(`../entry/src/main/ets/${relative}`, import.meta.url), 'utf8')
    .replace(/^import .* from .*;\r?\n/gm, '');
  const names = [...source.matchAll(/export\s+(?:class|enum)\s+(\w+)/g)].map(match => match[1]);
  const javascript = stripTypeScriptTypes(source.replace(/\bexport\s+/g, ''), { mode: 'transform' });
  return runInNewContext(`${javascript}\n({${names.join(',')}})`, { Error, ...dependencies });
}
const { ApiResponseParser } = load('data/ApiResponse.ets');
const { ChaoxingStatusMapper } = load('data/chaoxing/ChaoxingAccount.ets');

function repositoryWithResponse(status, body, initial = null) {
  let first = initial !== null;
  const http = {
    RequestMethod: { GET: 'GET', POST: 'POST' },
    createHttp: () => ({ request: async () => {
      if (first) { first = false; return { responseCode: 200, result: JSON.stringify(initial) }; }
      return { responseCode: status, result: JSON.stringify(body) };
    }, destroy() {} }),
  };
  const { ApiClient } = load('data/ApiClient.ets', {
    http, ApiResponseParser, RefreshCoordinator: class {}, AuthTokensModel: class {},
  });
  const { ChaoxingRepository } = load('data/chaoxing/ChaoxingRepository.ets', { http, ChaoxingStatusMapper });
  return new ChaoxingRepository(new ApiClient('https://example.invalid/api/v1', () => ''));
}

test('damaged credentials survive HTTP parsing and require reconnect for status and sync', async () => {
  const previous = ChaoxingStatusMapper.fromResponse({ status: 'online', courses: 4, last_synced_at: 'saved' });
  const repository = repositoryWithResponse(503, { code: 'CHAOXING_CREDENTIALS_UNAVAILABLE' }, { status: 'online', courses: 4, last_synced_at: 'saved' });
  await repository.getStatus();
  const status = await repository.getStatus();
  assert.equal(status.rawStatus, 'expired');
  assert.equal(status.requiresLogin, true);
  assert.equal(status.courses, 4);
  assert.match(status.warnings[0], /重新连接学习通/);
  await assert.rejects(repository.sync(), error => {
      assert.equal(error.statusCode, 503);
      assert.equal(error.backendCode, 'CHAOXING_CREDENTIALS_UNAVAILABLE');
      const account = ChaoxingStatusMapper.fromFailure(error, previous);
      assert.equal(account.rawStatus, 'expired');
      assert.equal(account.requiresLogin, true);
      assert.equal(account.connected, false);
      assert.equal(account.canSync, false);
      assert.equal(account.courses, 4);
      assert.equal(account.lastSyncedAt, 'saved');
      return true;
    });
});

test('transient HTTP failures retain the connection and never request rebinding', async () => {
  const previous = ChaoxingStatusMapper.fromResponse({ status: 'online', courses: 4 });
  for (const [status, body] of [[503, {}], [500, { code: 'CHAOXING_CREDENTIALS_UNAVAILABLE' }]]) {
    const repository = repositoryWithResponse(status, body, { status: 'online', courses: 4 });
    await repository.getStatus();
    const preserved = await repository.getStatus();
    assert.equal(preserved.connected, true);
    assert.equal(preserved.requiresLogin, false);
    assert.equal(preserved.rawStatus, 'unavailable');
    assert.equal(preserved.courses, 4);
    assert.equal((await repositoryWithResponse(status, body).getStatus()).requiresLogin, false);
    await assert.rejects(repository.sync(), error => {
      const account = ChaoxingStatusMapper.fromFailure(error, previous);
      assert.equal(account.rawStatus, 'unavailable');
      assert.equal(account.connected, true);
      assert.equal(account.requiresLogin, false);
      assert.equal(account.canSync, false);
      assert.equal(account.courses, 4);
      assert.equal(ChaoxingStatusMapper.fromFailure(error, ChaoxingStatusMapper.unavailable()).requiresLogin, false);
      const expired = ChaoxingStatusMapper.fromResponse({ status: 'expired' });
      assert.equal(ChaoxingStatusMapper.fromFailure(error, expired).rawStatus, 'expired');
      return true;
    });
  }
});

test('malformed envelopes do not fabricate a credential failure', () => {
  for (const body of ['', 'null', '<html>Unavailable</html>', '{"code":123}', '[]']) {
    assert.equal(ApiResponseParser.errorCode(body), '');
  }
});

test('successful login remains bound when its follow-up status check fails', async () => {
  const http = { RequestMethod: { GET: 'GET', POST: 'POST' } };
  const { ChaoxingRepository } = load('data/chaoxing/ChaoxingRepository.ets', { http, ChaoxingStatusMapper });
  for (const initial of ['offline', 'expired']) {
    let calls = 0;
    const repository = new ChaoxingRepository({
      request: async () => {
        if (++calls === 1) return { status: initial, courses: 4 };
        const error = new Error('服务暂时不可用'); error.statusCode = 503;
        throw error;
      },
      requestVoidWithoutAuthRefresh: async () => {},
      requestVoid: async () => {},
    });
    await repository.getStatus();
    await repository.login('synthetic', 'synthetic');
    const account = await repository.getStatus();
    assert.equal(account.rawStatus, 'unavailable');
    assert.equal(account.connected, true);
    assert.equal(account.requiresLogin, false);
    assert.equal(account.courses, 4);
  }
});

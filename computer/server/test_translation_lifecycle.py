import asyncio
import base64
import json
import sqlite3
from threading import Event
from typing import cast

from fastapi import WebSocket
import pytest

from computer.server.app import CommandError, SessionTransport
from computer.server.providers import TranslationResult
from computer.server.storage import SQLiteStore


def test_cancel_signals_provider_before_storage_and_releases_on_error(tmp_path, monkeypatch):
    transport = SessionTransport(SQLiteStore(tmp_path / 'state.db'), 30, lambda: object())
    session = transport._start({'source_lang': 'vi', 'target_lang': 'en'})
    live = transport.sessions[session.session_id]

    def unavailable(_session):
        assert live.cancelled.is_set()
        raise sqlite3.OperationalError('test storage error')

    monkeypatch.setattr(transport, '_record', unavailable)
    with pytest.raises(sqlite3.OperationalError):
        transport._cancel(session.session_id)
    assert session.session_id not in transport.sessions


@pytest.mark.parametrize(('command', 'expected'), [
    ('utterance.chunk', ['utterance.output', 'utterance.ack']),
    ('session.cancel', ['session.cancelled']),
])
def test_simultaneously_ready_receive_and_output(tmp_path, monkeypatch, command, expected):
    transport = SessionTransport(SQLiteStore(tmp_path / 'state.db'), 30, lambda: object())
    pcm = base64.b64encode(bytes(640)).decode('ascii')
    original_wait = asyncio.wait

    async def both_ready(tasks, *, return_when):
        return await original_wait(tasks, return_when=asyncio.ALL_COMPLETED)

    monkeypatch.setattr('computer.server.app.asyncio.wait', both_ready)
    original_respond = transport._respond

    async def respond(message, owned):
        if message['type'] == 'utterance.finish':
            return owned, {'type': 'utterance.output', 'message_id': 'finish'}
        return await original_respond(message, owned)

    monkeypatch.setattr(transport, '_respond', respond)

    class Socket:
        headers = {}
        replies = []
        index = 0

        async def accept(self):
            pass

        async def send_json(self, response):
            self.replies.append(response)

        async def receive(self):
            index = self.index
            self.index += 1
            if index == 3:
                return {'type': 'websocket.disconnect'}
            message = {'v': 1, 'message_id': str(index), 'payload': {}}
            if index == 0:
                message.update(type='session.start', payload={'source_lang': 'vi', 'target_lang': 'en'})
            else:
                message.update(type='utterance.finish' if index == 1 else command,
                               session_id=self.replies[0]['session_id'])
                if index == 2 and command == 'utterance.chunk':
                    message['payload'] = {'stream_id': 'a2b', 'seq': 0, 'data_b64': pcm}
            return {'type': 'websocket.receive', 'text': json.dumps(message)}

    socket = Socket()
    asyncio.run(transport.serve(cast(WebSocket, socket)))
    assert [response['type'] for response in socket.replies[1:]] == expected


def test_cancelled_worker_holds_capacity_until_it_really_exits(tmp_path, monkeypatch):
    monkeypatch.setattr('computer.server.app.MAX_PROVIDER_WORKERS', 1, raising=False)
    entered, release = Event(), Event()

    class Provider:
        def translate(self, audio, source, target):
            if audio == b'old':
                entered.set()
                assert release.wait(4)
            return TranslationResult(audio, '', '')

    async def scenario():
        transport = SessionTransport(SQLiteStore(tmp_path / 'state.db'), 30, Provider)
        old, new = [transport._start({'source_lang': 'vi', 'target_lang': 'en'}) for _ in range(2)]
        old_live, new_live = (transport.sessions[s.session_id] for s in (old, new))
        job = asyncio.create_task(transport._run_provider(old_live, b'old', 'vi', 'en'))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            transport._cancel(old.session_id)
            job.cancel()
            with pytest.raises(asyncio.CancelledError):
                await job
            with pytest.raises(CommandError) as failure:
                await transport._run_provider(new_live, b'new', 'vi', 'en')
            assert failure.value.code == 'provider_busy'
        finally:
            release.set()
        async with asyncio.timeout(2):
            while True:
                try:
                    result = await transport._run_provider(new_live, b'new', 'vi', 'en')
                    break
                except CommandError as exc:
                    assert exc.code == 'provider_busy'
                    await asyncio.sleep(0.01)
        assert result.audio == b'new'

    asyncio.run(scenario())

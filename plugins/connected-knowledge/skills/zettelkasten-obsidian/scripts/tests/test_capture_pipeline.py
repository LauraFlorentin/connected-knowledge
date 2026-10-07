"""Capture pipeline: machine config, enqueue-only hooks, sweep, labels and safety.

Standard library only (no PyYAML), so CI can run this module on Python 3.9.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from ck_fixtures import Claude, Codex, Machine, PLUGIN, SCRIPTS
import ck_capture
import ck_config
import ck_render
import ck_sweep
import ck_transcripts

HOOK = PLUGIN/'hooks/capture.py'


def tree_size(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file())


class Base(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.cfg = ck_config.validate(self.m.cfg)
        self.garden = self.m.projects/'garden'

    def tearDown(self):
        self.m.cleanup()

    def claude(self, sid='11111111-aaaa-4bbb-8ccc-000000000001', cwd=None):
        return Claude(sid, cwd or self.garden)

    def queue(self, path, sid, event='Stop', cwd=None):
        paths = ck_config.state(self.cfg)
        return ck_config.enqueue(paths, 'claude-code', {'hook_event_name': event, 'session_id': sid,
                                                        'transcript_path': str(path), 'cwd': str(cwd or self.garden)})

    def notes(self):
        return sorted((self.m.vault/'Sources/AI Conversations').rglob('*.md'))

    def transcripts(self):
        return sorted((self.m.vault/'Attachments/AI Transcripts').rglob('*.md'))

    def hook(self, event, env=None, config=True):
        if config:
            self.m.config_file()
        environment = self.m.env(CLAUDE_PLUGIN_ROOT=str(PLUGIN), **(env or {}))
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), env=environment,
                              capture_output=True, text=True, timeout=60)


class MachineConfig(Base):
    def test_hook_finds_config_without_environment_variables(self):
        event = {'hook_event_name': 'Stop', 'session_id': 'abc', 'cwd': str(self.garden),
                 'transcript_path': str(self.m.claude/'missing.jsonl')}
        result = self.hook(event)
        self.assertEqual((result.returncode, result.stdout), (0, '{}\n'), result.stderr)
        queued = list((self.m.state/'queue').glob('*.json'))
        self.assertEqual(len(queued), 1)
        self.assertEqual(json.loads(queued[0].read_text())['session_id'], 'abc')

    def test_hook_is_inert_until_capture_is_switched_on(self):
        self.m.cfg['capture']['enabled'] = False
        event = {'hook_event_name': 'Stop', 'session_id': 'abc', 'cwd': str(self.garden),
                 'transcript_path': str(self.m.claude/'x.jsonl')}
        self.assertEqual(self.hook(event).returncode, 0)
        self.assertFalse(self.m.state.exists())
        # No machine configuration and no legacy variables: nothing happens at all.
        result = self.hook('not JSON', config=False)
        self.assertEqual((result.returncode, result.stdout), (0, '{}\n'))
        self.assertFalse(self.m.state.exists())

    def test_hook_never_opens_the_transcript(self):
        path = self.claude().user('Fictional question').save(self.m.claude/'p')
        path.chmod(0)  # unreadable: any attempt to open it would fail the hook
        try:
            event = {'hook_event_name': 'Stop', 'session_id': 'abc', 'cwd': str(self.garden),
                     'transcript_path': str(path)}
            result = self.hook(event)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list((self.m.state/'queue').glob('*.json'))), 1)
        finally:
            path.chmod(0o600)

    def test_out_of_scope_and_subagent_events_are_not_queued(self):
        for event in ({'hook_event_name': 'Stop', 'session_id': 'a', 'cwd': str(self.m.root),
                       'transcript_path': '/x.jsonl'},
                      {'hook_event_name': 'Stop', 'session_id': 'b', 'cwd': str(self.garden),
                       'transcript_path': '/x.jsonl', 'agent_id': 'child'}):
            self.assertEqual(self.hook(event).returncode, 0)
        self.assertFalse(list((self.m.state/'queue').glob('*.json')) if self.m.state.exists() else [])
        self.m.cfg['capture']['exclude'] = [str(self.garden)]
        self.hook({'hook_event_name': 'Stop', 'session_id': 'c', 'cwd': str(self.garden/'beds'),
                   'transcript_path': '/x.jsonl'})
        self.assertFalse(list((self.m.state/'queue').glob('*.json')) if self.m.state.exists() else [])

    def test_state_must_stay_outside_the_vault(self):
        bad = dict(self.m.cfg, state=str(self.m.vault/'state'))
        with self.assertRaises(ValueError):
            ck_config.validate(bad)
        with self.assertRaises(ValueError):
            ck_config.private_dir(self.m.vault/'x', self.m.vault)

    def test_private_folders_are_0700_and_files_0600(self):
        path = self.claude().user('Fictional question').assistant('Fictional answer').save(self.m.claude/'p')
        ck_sweep.capture_file(self.cfg, 'claude-code', path, apply=True)
        for folder in ('', 'queue', 'raw', 'locks'):
            self.assertEqual((self.m.state/folder).stat().st_mode & 0o777, 0o700, folder)
        self.assertEqual((self.m.state/'manifest.json').stat().st_mode & 0o777, 0o600)
        raw = next((self.m.state/'raw').rglob('*.jsonl'))
        self.assertEqual(raw.stat().st_mode & 0o777, 0o600)
        self.assertEqual(raw.read_bytes(), path.read_bytes())

    def test_saving_validates_and_reloads(self):
        path = ck_config.save(self.m.cfg, self.m.root/'cfg/config.json')
        self.assertEqual(ck_config.load(path)['machine'], 'mac-mini')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(ValueError):
            ck_config.validate(dict(self.m.cfg, machine='Mac Mini!'))


class Sweep(Base):
    def test_sixty_turns_bound_state_and_write_one_note(self):
        session, sid = self.claude(), '11111111-aaaa-4bbb-8ccc-000000000001'
        path = None
        for turn in range(60):
            session.user('Fictional question %d about raised garden beds. ' % turn + 'Soil and sun. ' * 20)
            session.assistant('Fictional answer %d. ' % turn + 'Mulch and water. ' * 20, tools=['Write'])
            path = session.save(self.m.claude/'garden')
            self.queue(path, sid)
            self.assertEqual(ck_sweep.sweep(self.cfg, only={sid})['status'], 'done')
        self.assertEqual(len(self.notes()), 1)
        self.assertEqual(len(self.transcripts()), 1)
        self.assertLessEqual(tree_size(self.m.state), 2 * path.stat().st_size)
        allowed = ('Sources/', 'Attachments/', '_meta/index/', 'Projects/')
        self.assertTrue(all(f.startswith(allowed) for f in self.m.vault_files()), self.m.vault_files())
        self.assertIn('120 messages', self.notes()[0].read_text())

    def test_idle_rule_waits_then_captures(self):
        path = self.claude().user('Fictional question').save(self.m.claude/'garden')
        entry = self.queue(path, '11111111-aaaa-4bbb-8ccc-000000000001')
        self.assertEqual(ck_sweep.sweep(self.cfg)['waiting'], 1)
        self.assertEqual(self.notes(), [])
        later = time.time() + 11 * 60
        self.assertEqual(ck_sweep.sweep(self.cfg, now=later)['captured'], 1)
        self.assertFalse(entry.exists())

    def test_session_end_captures_at_once(self):
        path = self.claude().user('Fictional question').save(self.m.claude/'garden')
        self.queue(path, '11111111-aaaa-4bbb-8ccc-000000000001', event='SessionEnd')
        self.assertEqual(ck_sweep.sweep(self.cfg)['captured'], 1)

    def test_killed_sweep_is_followed_by_a_successful_one(self):
        path = self.claude().user('Fictional question').assistant('Fictional answer').save(self.m.claude/'garden')
        sid = '11111111-aaaa-4bbb-8ccc-000000000001'
        self.queue(path, sid, event='SessionEnd')
        paths = ck_config.state(self.cfg)
        holder = subprocess.Popen([sys.executable, '-c', (
            'import sys,time; sys.path.insert(0,%r); import ck_config\n'
            'with ck_config.try_lock(%r) as got:\n print(got, flush=True); time.sleep(60)')
            % (str(SCRIPTS), str(paths['locks']/'capture.lock'))], stdout=subprocess.PIPE, text=True)
        self.assertEqual(holder.stdout.readline().strip(), 'True')
        self.assertEqual(ck_sweep.sweep(self.cfg)['status'], 'busy')
        holder.send_signal(signal.SIGKILL)
        holder.wait()
        holder.stdout.close()
        # A crash half-way through the writes leaves the queue entry for a retry.
        real = ck_capture.write_atomic
        calls = []

        def flaky(target, data, mode=0o600):
            calls.append(target)
            if len(calls) == 2:
                raise OSError('simulated crash')
            return real(target, data, mode)
        with mock.patch.object(ck_capture, 'write_atomic', flaky):
            self.assertEqual(ck_sweep.sweep(self.cfg)['retry'], 1)
        self.assertEqual(len(list(paths['queue'].glob('*.json'))), 1)
        report = ck_sweep.sweep(self.cfg)
        self.assertEqual(report['captured'], 1, report)
        self.assertEqual((len(self.notes()), len(self.transcripts())), (1, 1))

    def test_two_sweeps_at_once_neither_fails(self):
        for n in range(3):
            sid = '11111111-aaaa-4bbb-8ccc-00000000000%d' % n
            path = Claude(sid, self.garden).user('Fictional question %d' % n).save(self.m.claude/'garden')
            self.queue(path, sid, event='SessionEnd')
        self.m.config_file()
        command = [sys.executable, str(SCRIPTS/'ck_sweep.py')]
        runs = [subprocess.Popen(command, env=self.m.env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for _ in range(2)]
        outputs = [run.communicate(timeout=60) for run in runs]
        self.assertEqual([run.returncode for run in runs], [0, 0], outputs)
        statuses = sorted(json.loads(out)['status'] for out, _ in outputs)
        self.assertIn(statuses, (['busy', 'done'], ['done', 'done']))
        self.assertEqual(len(self.notes()), 3)

    def test_a_turn_that_ends_during_capture_stays_queued(self):
        sid = '11111111-aaaa-4bbb-8ccc-000000000001'
        path = self.claude().user('Fictional question').save(self.m.claude/'garden')
        entry = self.queue(path, sid, event='SessionEnd')
        real = ck_capture.capture

        def busy(*args, **kwargs):
            self.queue(path, sid)  # the next Stop arrives while the sweep is writing
            return real(*args, **kwargs)
        with mock.patch.object(ck_capture, 'capture', busy):
            self.assertEqual(ck_sweep.sweep(self.cfg)['captured'], 1)
        self.assertTrue(entry.exists())
        self.assertEqual(ck_sweep.sweep(self.cfg)['unchanged'], 1)
        self.assertFalse(entry.exists())

    def test_quiet_sessions_elsewhere_are_noticed_at_the_end_of_a_turn(self):
        paths = ck_config.state(self.cfg)
        current = self.queue(self.m.claude/'a.jsonl', 'current')
        self.assertFalse(ck_sweep.others_due(self.cfg, paths, current.name))
        self.queue(self.m.claude/'b.jsonl', 'other')
        self.assertFalse(ck_sweep.others_due(self.cfg, paths, current.name))
        self.assertTrue(ck_sweep.others_due(self.cfg, paths, current.name, now=time.time() + 11 * 60))
        self.queue(self.m.claude/'b.jsonl', 'other', event='SessionEnd')
        self.assertTrue(ck_sweep.others_due(self.cfg, paths, current.name))

    def test_failures_are_retried_then_parked(self):
        path = self.m.claude/'garden/broken.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text('{"not": "a session"}\n')
        self.queue(path, 'broken', event='SessionEnd')
        for _ in range(ck_sweep.MAX_ATTEMPTS):
            ck_sweep.sweep(self.cfg)
        self.assertEqual(list((self.m.state/'queue').glob('*.json')), [])
        self.assertEqual(len(list((self.m.state/'failed').glob('*.json'))), 1)
        self.assertIn('claude-code:broken', json.loads((self.m.state/'attention.json').read_text()))


class Labels(Base):
    def capture(self, session, overrides=None, apply=True, folder='garden'):
        path = session.save(self.m.claude/folder)
        return ck_sweep.capture_file(self.cfg, 'claude-code', path, overrides, apply=apply)

    def test_three_directory_session_belongs_to_its_first_directory(self):
        session = self.claude().user('Fictional start').move(self.garden/'beds').assistant('Moved')
        session.move(self.m.projects/'orchard').user('Fictional elsewhere')
        report = self.capture(session)
        self.assertEqual(report['project'], 'Projects/garden')
        text = self.notes()[0].read_text()
        self.assertIn('project: "[[Projects/garden]]"', text)
        self.assertNotIn(str(self.m.root), text + self.transcripts()[0].read_text())
        self.assertTrue((self.m.vault/'Projects/garden.md').exists())

    def test_meta_and_wrapper_rows_are_not_rendered_as_user_text(self):
        session = self.claude().harness().user('<system-reminder>Fictional reminder</system-reminder>Plant beans')
        session.assistant('Fictional reply').tool_result().assistant('Second part', tools=['Write'])
        self.capture(session)
        transcript = self.transcripts()[0].read_text()
        self.assertNotIn('Caveat', transcript)
        self.assertNotIn('Fictional output', transcript)
        self.assertNotIn('Fictional reminder', transcript)
        self.assertIn('## 1 · Command', transcript)
        self.assertIn('`/ck-help`', transcript)
        self.assertIn('## 2 · You', transcript)
        self.assertIn('Plant beans', transcript)
        self.assertEqual(transcript.count('· Claude'), 1)  # one assistant turn from two rows
        self.assertIn('_Tools used: Write_', transcript)
        self.assertIn('system or harness messages are left out', self.notes()[0].read_text())

    def test_title_sources_in_order(self):
        base = self.claude().user('Please help plan fictional raised garden beds today')
        self.assertEqual(self.capture(base, apply=False)['title'], 'Please help plan fictional raised')
        base.title('summary', 'Garden bed planning')
        self.assertEqual(self.capture(base, apply=False)['title'], 'Garden bed planning')
        base.title('custom-title', 'Beds for spring planting season ahead')
        self.assertEqual(self.capture(base, apply=False)['title'], 'Beds for spring planting season')
        self.assertEqual(self.capture(base, {'title': 'My chosen title'}, apply=False)['title'], 'My chosen title')
        with self.assertRaises(ValueError):
            self.capture(base, {'title': 'one two three four five six'}, apply=False)

    def test_labels_and_file_names(self):
        self.m.cfg['capture']['default_remote_device'] = 'macbook-air'
        session = self.claude().user('Fictional question').assistant('Fictional answer')
        report = self.capture(session, {'category': 'Personal'})
        note = self.notes()[0]
        self.assertTrue(note.name.startswith('2026-10-06 Fictional question — claude-code 11111111'), note.name)
        self.assertEqual(note.parent.name, '2026')
        meta, _ = ck_render.split_note(note.read_text())
        for key, value in {'schema_version': 1, 'note_type': 'source', 'category': 'Personal',
                           'classification_status': 'provisional', 'source_platform': 'Claude Code',
                           'source_account': 'personal', 'source_machine': 'mac-mini',
                           'source_device': 'mac-mini', 'source_surface': 'cli',
                           'source_id': '11111111-aaaa-4bbb-8ccc-000000000001'}.items():
            self.assertEqual(meta[key], value, key)
        self.assertTrue(meta['id'].startswith('ck-') and len(meta['id']) == 19)
        self.assertRegex(meta['source_created'], r'^2026-10-06T\d\d:\d\d:\d\d[+-]\d\d:\d\d$')
        self.assertEqual(report['device'], 'mac-mini')
        index = (self.m.vault/'_meta/index/conversations.mac-mini.jsonl').read_text().splitlines()
        self.assertEqual(json.loads(index[0])['id'], meta['id'])

    def test_remote_control_device_comes_from_the_machine_default(self):
        self.m.cfg['capture']['default_remote_device'] = 'macbook-air'
        session = self.claude().user('Fictional question')
        self.assertEqual(self.capture(session, {'surface': 'remote-control'}, apply=False)['device'], 'macbook-air')
        self.assertEqual(self.capture(session, {'surface': 'remote-control', 'device': 'iphone'}, apply=False)['device'], 'iphone')

    def test_codex_real_shape(self):
        session = Codex('019a0000-1111-7222-8333-444455556666', self.m.projects/'orchard').harness()
        session.message('user', 'Count the fictional pears').tool('shell').message('assistant', 'Twelve fictional pears.')
        session.turn(self.m.projects/'orchard/b')
        path = session.save(self.m.codex)
        report = ck_sweep.capture_file(self.cfg, 'codex', path, apply=True)
        self.assertEqual((report['status'], report['project'], report['messages']), ('created', 'Projects/orchard', 2))
        transcript = self.transcripts()[0].read_text()
        self.assertNotIn('environment_context', transcript)
        self.assertNotIn('AGENTS.md', transcript)
        self.assertNotIn('developer instructions', transcript)
        self.assertIn('_Tools used: shell_', transcript)
        self.assertIn('· Codex', transcript)

    def test_partial_final_line_is_tolerated_while_a_session_runs(self):
        session = self.claude().user('Fictional question')
        path = session.save(self.m.claude/'garden')
        path.write_bytes(path.read_bytes() + b'{"type": "assist')
        self.assertEqual(ck_sweep.capture_file(self.cfg, 'claude-code', path)['status'], 'preview')

    def test_preview_writes_nothing(self):
        report = self.capture(self.claude().user('Fictional question'), apply=False)
        self.assertEqual((report['status'], report['would']), ('preview', 'created'))
        self.assertEqual(self.m.vault_files(), [])
        self.assertFalse(self.m.state.exists())

    def test_transcript_outside_the_transcript_folders_is_refused(self):
        path = self.claude().user('Fictional').save(self.m.root/'elsewhere')
        with self.assertRaises(ValueError):
            ck_sweep.capture_file(self.cfg, 'claude-code', path)


class Updates(Base):
    def setUp(self):
        super().setUp()
        self.session = self.claude().user('Fictional question').assistant('Fictional answer')
        self.path = self.session.save(self.m.claude/'garden')
        ck_sweep.capture_file(self.cfg, 'claude-code', self.path, apply=True)
        self.note = self.notes()[0]

    def grow(self):
        self.session.user('A follow-up').assistant('A fictional follow-up answer')
        self.session.save(self.m.claude/'garden')
        return ck_sweep.capture_file(self.cfg, 'claude-code', self.path, apply=True)

    def test_repeat_is_unchanged(self):
        self.assertEqual(ck_sweep.capture_file(self.cfg, 'claude-code', self.path, apply=True)['status'], 'unchanged')

    def test_person_edits_survive_updates(self):
        text = self.note.read_text().replace('classification_status: "provisional"', 'classification_status: "reviewed"')
        text = text.replace('## My notes\n', '## My notes\nMy own fictional thought.\n')
        text = text.replace('topics: []', 'topics:\n  - "[[Maps/Gardening]]"\nmood: "sunny"')
        text = text.replace('title: "Fictional question"', 'title: "Renamed by me"')
        self.note.write_text(text)
        self.assertEqual(self.grow()['status'], 'updated')
        after = self.note.read_text()
        meta, _ = ck_render.split_note(after)
        self.assertIn('My own fictional thought.', after)
        self.assertEqual((meta['classification_status'], meta['mood'], meta['title']), ('reviewed', 'sunny', 'Renamed by me'))
        self.assertEqual(meta['topics'], ['[[Maps/Gardening]]'])
        self.assertIn('4 messages', after)
        self.assertIn('# Renamed by me', after)

    def test_removed_markers_stop_the_update(self):
        self.note.write_text(self.note.read_text().replace(ck_render.MARK_END, ''))
        before = self.note.read_bytes()
        self.assertEqual(self.grow()['status'], 'conflict')
        self.assertEqual(self.note.read_bytes(), before)

    def test_shorter_transcript_never_replaces_a_capture(self):
        self.grow()
        before = self.note.read_bytes()
        self.session.rows = self.session.rows[:1]
        self.session.save(self.m.claude/'garden')
        self.assertEqual(ck_sweep.capture_file(self.cfg, 'claude-code', self.path, apply=True)['status'], 'diverged')
        self.assertEqual(self.note.read_bytes(), before)

    def test_hand_edited_transcript_is_kept(self):
        transcript = self.transcripts()[0]
        transcript.write_text(transcript.read_text() + '\nedited')
        self.assertEqual(self.grow()['status'], 'conflict')
        self.assertTrue(transcript.read_text().endswith('edited'))

    def test_deleted_note_is_not_recreated_by_the_sweep(self):
        self.note.unlink()
        self.assertEqual(self.grow()['status'], 'deleted')
        self.assertFalse(self.note.exists())


class Foreign(Base):
    def setUp(self):
        super().setUp()
        self.path = self.claude().user('Fictional question').save(self.m.claude/'garden')
        self.target = self.m.vault/ck_sweep.capture_file(self.cfg, 'claude-code', self.path)['note']

    def test_different_note_at_the_target_path_stops(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('---\nid: "someone-else"\n---\nTheirs\n')
        self.assertEqual(ck_sweep.capture_file(self.cfg, 'claude-code', self.path, apply=True)['status'], 'conflict')
        self.assertEqual(self.target.read_text(), '---\nid: "someone-else"\n---\nTheirs\n')

    def test_same_conversation_from_another_mac_is_left_alone(self):
        other = Machine('macbook-air')
        try:
            other_cfg = dict(self.m.cfg, machine='macbook-air', state=str(other.state))
            ck_sweep.capture_file(other_cfg, 'claude-code', self.path, apply=True)
            before = self.target.read_bytes()
            report = ck_sweep.capture_file(self.cfg, 'claude-code', self.path, apply=True)
            self.assertEqual(report['status'], 'elsewhere')
            self.assertEqual(self.target.read_bytes(), before)
        finally:
            other.cleanup()


class Python39(unittest.TestCase):
    def run_capture(self, python):
        code = ('import json,sys; sys.path.insert(0,%r); sys.path.insert(0,%r)\n'
                'from ck_fixtures import Claude, Machine; import ck_config, ck_sweep\n'
                'm=Machine(); cfg=ck_config.validate(m.cfg)\n'
                'p=Claude("s-1", m.projects/"garden").user("Fictional").assistant("Reply").save(m.claude/"g")\n'
                'r=ck_sweep.capture_file(cfg,"claude-code",p,apply=True); print(r["status"]); m.cleanup()\n'
                'assert "yaml" not in sys.modules') % (str(SCRIPTS), str(Path(__file__).parent))
        return subprocess.run([python, '-S', '-c', code], capture_output=True, text=True, timeout=60)

    def test_capture_needs_no_third_party_package(self):
        result = self.run_capture(sys.executable)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'created'), result.stderr)

    @unittest.skipUnless(shutil.which('python3.9') or (Path('/usr/bin/python3').exists() and subprocess.run(
        ['/usr/bin/python3', '-c', 'import sys; sys.exit(sys.version_info[:2] != (3, 9))']).returncode == 0),
        'no Python 3.9 interpreter on this machine')
    def test_capture_runs_on_python_39(self):
        python = shutil.which('python3.9') or '/usr/bin/python3'
        result = self.run_capture(python)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'created'), result.stderr)


if __name__ == '__main__':
    unittest.main()

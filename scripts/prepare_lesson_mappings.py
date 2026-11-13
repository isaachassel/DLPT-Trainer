"""Build provisional question-level competency mappings without changing audio."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_vocabulary_passages import build


def question(identifier, prompt, correct, wrong, explanation, evidence):
    return dict(id=identifier, prompt=prompt, answer=correct, distractors=wrong,
                explanation=explanation, evidence=evidence)


def build_mappings():
    passages = build()['passages']
    mappings = []
    for p in passages:
        questions = [question(t['id'] + '_lexical', f'What does “{t["target"]}” mean in this conversation?',
                              t['meaning'], t['distractors'],
                              f'Here “{t["target"]}” means {t["meaning"]}.', t['target'])
                     for t in p['targets'][:2]]
        mappings.append(dict(id=p['id'] + '_lexical', passage_id=p['id'], category='lexical',
                             objective='Recognize the contextual meanings of ' + ' and '.join(t['term'] for t in p['targets'][:2]),
                             lesson_id='ru-basic-mod6-l32' if p.get('lesson') == 'Lesson 32' else None,
                             review_guidance='Review the target word senses, then try them in a fresh context.', questions=questions))

    def add(pid, category, objective, guidance, specs):
        mappings.append(dict(id=pid + '_' + category, passage_id=pid, category=category,
                             lesson_id='ru-basic-mod6-l32' if pid.startswith('vocab_l32_') else None,
                             objective=objective, review_guidance=guidance,
                             questions=[question(f'{pid}_{category}_{n}', *spec) for n, spec in enumerate(specs, 1)]))

    add('vocab_l32_movement', 'structural', 'Distinguish one-time and repeated motion',
        'Compare вести/водить, везти/возить, and нести/носить. Identify whether a sentence describes one trip or repeated trips.', [
        ('Why is “возить” appropriate for the driver’s work?', 'He will make several trips between buildings.',
         ['He will make only one trip on foot.', 'He will wear a badge.', 'He will stay in the exhibition hall.'],
         'Возить describes repeated transport by vehicle; the next turn confirms several trips.', 'Водитель сделает несколько поездок.'),
        ('What does “пока всё не перенесёт” tell us about Anton’s task?', 'He will keep carrying boxes until everything has been moved.',
         ['He must stop before moving any boxes.', 'He has already moved everything.', 'He will move just one box tomorrow.'],
         'Пока … не with this completed action marks the endpoint: until everything is moved, not a ban on moving it.', 'пока всё не перенесёт')])

    add('vocab_l32_orders', 'structural', 'Recognize task descriptions and completed actions',
        'Compare describing an assigned task with reporting its completion; review удалось + infinitive.', [
        ('What does “удалось выполнить” establish?', 'The writer successfully completed the work.',
         ['The writer only intended to start.', 'The writer refused the work.', 'The writer was still waiting for permission.'],
         'Удалось + perfective выполнить reports successful completion, supported by вовремя.', 'Автору удалось выполнить работу вовремя.'),
        ('What is the purpose of “чтобы” in the description of his task?', 'It introduces what he was assigned to do.',
         ['It denies that a task existed.', 'It compares two soldiers.', 'It reports someone else’s exact words.'],
         'Состояла в том, чтобы introduces the content of the task: sorting books and making a list.', 'Его задача состояла в том, чтобы разобрать книги')])

    add('vocab_l32_history', 'discourse', 'Compare accounts and distinguish evidence from overstatement',
        'Identify contrasts between sources and the evidence supporting or limiting a summary.', [
        ('How does the second account differ from the first?', 'It emphasizes time gained through defense rather than just defeat.',
         ['It says no fighting took place.', 'It gives an identical explanation of defeat.', 'It describes an unrelated museum visit.'],
         'Не совсем introduces a contrast, followed by the defensive benefit emphasized in the second account.', 'оборона позволила выиграть время'),
        ('Why does the speaker avoid saying there was complete encirclement?', 'A route out remained, so the claim would overstate the evidence.',
         ['Neither account mentions a location.', 'The map proves all roads were blocked.', 'The speaker does not know which side retreated.'],
         'The open road is the reason given for rejecting that description.', 'На карте оставалась дорога для выхода.')])

    add('vocab_l32_report', 'discourse', 'Track correction and uncertainty in a summary',
        'Distinguish confirmed events, a speaker’s correction, and information that remains uncertain.', [
        ('What change does the speaker agree to make?', 'Remove the claim that the whole building was destroyed.',
         ['Add that people died inside.', 'Say the explosion never happened.', 'Blame the journalist for the explosion.'],
         'The speaker concedes that only part was damaged and the stronger claim must be removed.', 'повреждена только одна часть'),
        ('What is the main purpose of the final part of the conversation?', 'To make the summary accurate and identify unconfirmed information.',
         ['To accuse a suspect immediately.', 'To describe how to demolish a building.', 'To advertise a new recording device.'],
         'The ending emphasizes accurate sequence and explicitly marking what is not confirmed.', 'отмечу, какие сведения ещё не подтверждены')])

    add('vocab_classroom', 'sociocultural', 'Recognize informal peer register and a supportive suggestion',
        'Notice ты and давай in a peer conversation. Interpret suggestions in context; these examples do not establish rules for all Russian speakers.', [
        ('What does the opening “Ты уже подготовился…” suggest about the register?', 'The speakers are using informal, familiar address.',
         ['The speaker is using formal plural address.', 'It is an impersonal official announcement.', 'The speaker is addressing a large public audience.'],
         'Ты is informal singular address. It does not by itself establish the speakers’ exact relationship.', 'Ты уже подготовился'),
        ('What is the speaker doing by saying “Давай посмотрим вместе”?', 'Offering to work through the problem together.',
         ['Ordering the other person to leave.', 'Refusing further discussion.', 'Demanding that the teacher grade the work immediately.'],
         'Давай with together frames a collaborative suggestion in this conversation.', 'Давай посмотрим вместе.')])

    add('vocab_clothing', 'sociocultural', 'Understand a sales interaction and its stated return conditions',
        'Identify the seller’s advice and the conditions stated in this specific transaction. Do not assume these are universal store policies.', [
        ('Why does the salesperson say the light jacket will not do?', 'To advise the customer about suitability for a cold-weather trip.',
         ['To announce that the shop is closed.', 'To refuse all service to the customer.', 'To demand a receipt before showing any clothing.'],
         'The advice responds to the customer’s destination and the expected cold.', 'для сильного холода она не подойдёт'),
        ('What must the customer do to use the return offer described here?', 'Keep the receipt and leave the tag on, returning within a week.',
         ['Remove the tag and return at any time.', 'Wear the coat for a month first.', 'Return only if the colour is black.'],
         'These are conditions of this seller’s offer, not a claim about Russian consumer law.', 'если сохранить чек и не снимать ярлык')])

    return dict(version=1, review_status='provisional',
                authoring='Author-created competency mappings; not reviewed or endorsed by SLS/DLI.',
                lessons=[dict(id='ru-basic-mod6-l32', language='ru', module='Mod 6', lesson='Lesson 32',
                              title='Armed forces and military actions',
                              resource='Russian Basic Course, Module VI, Lesson 32. Glossary: printed pp. 85–88. Grammar: use the Lesson 32 contents to locate the relevant explanation.')],
                mappings=mappings)


if __name__ == '__main__':
    data = build_mappings()
    (ROOT / 'data/study/lesson_mappings.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{len(data['mappings'])} two-question mappings; no audio changed")

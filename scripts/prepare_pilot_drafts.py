"""Reproducible original draft scripts; no API calls and no generated audio."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.dialogue_authoring import DialogueDraft, DraftQuestion, materialize
from core.preset_bank import ContentPackage, ROOT, Turn, write_package

# topic, relationship, alternating turns, two English questions (correct option first), evidence
DIALOGUES = [
    ("Dinner", "Wife and husband", ["Что у нас сегодня на ужин?", "Рыба и картошка.", "Хорошо. Во сколько будем есть?", "В семь. Помой, пожалуйста, помидоры.", "Сейчас помою. Сделаем салат?", "Да, сделаем."],
     [("What will they eat for dinner?", ["Fish and potatoes", "Chicken and rice", "Soup and bread", "Pasta and cheese"], "Рыба и картошка."), ("When will they eat?", ["At seven", "At six", "At eight", "At nine"], "В семь.")]),
    ("Shopping", "Wife and husband", ["Я иду в магазин. Что купить?", "Купи молоко и хлеб.", "А яйца дома есть?", "Да, яйца есть. Возьми ещё два яблока.", "Красные или зелёные?", "Красные, пожалуйста."],
     [("What should the shopper buy besides fruit?", ["Milk and bread", "Butter and cheese", "Rice and fish", "Tea and sugar"], "Купи молоко и хлеб."), ("How many apples are requested?", ["Two", "Three", "Four", "Five"], "Возьми ещё два яблока.")]),
    ("Cleaning", "Wife and husband", ["Давай уберём квартиру.", "Хорошо. Я помою пол на кухне.", "А я помою посуду.", "Где ведро?", "В ванной, у двери.", "Спасибо, нашёл."],
     [("Which room's floor will the husband wash?", ["The kitchen", "The bedroom", "The bathroom", "The living room"], "Я помою пол на кухне."), ("Where is the bucket?", ["In the bathroom", "On the balcony", "In the kitchen", "In the hallway"], "В ванной, у двери.")]),
    ("Weekend", "Wife and husband", ["Что будем делать в субботу?", "Поедем к твоей маме?", "Давай. Она будет дома.", "Поедем утром?", "Нет, после обеда, в три.", "Хорошо. Купим ей цветы."],
     [("Whom will they visit?", ["The wife's mother", "The husband's father", "Their neighbour", "Their daughter"], "Поедем к твоей маме?"), ("When will they leave?", ["At three", "At one", "At five", "At seven"], "Нет, после обеда, в три.")]),
    ("Meeting", "Two friends", ["Привет! Встретимся завтра?", "Да. Давай у кафе.", "В какое время?", "В десять утра.", "Хорошо. Я приду пешком.", "Тогда до завтра!"],
     [("Where will the friends meet?", ["By a cafe", "By a school", "By a pharmacy", "By a bank"], "Давай у кафе."), ("At what time will they meet?", ["Ten in the morning", "Eight in the morning", "Six in the evening", "Nine in the evening"], "В десять утра.")]),
    ("Transport", "Two neighbours", ["Ты сегодня едешь на работу на машине?", "Нет, на автобусе. Машина в ремонте.", "Какой автобус тебе нужен?", "Номер пять.", "Остановка рядом?", "Да, напротив магазина."],
     [("How will the person travel to work?", ["By bus", "By car", "By train", "By bicycle"], "Нет, на автобусе."), ("Which bus is needed?", ["Number five", "Number two", "Number eight", "Number ten"], "Номер пять.")]),
    ("Weather", "Wife and husband", ["На улице холодно?", "Да, и идёт дождь.", "Тогда надену куртку.", "Возьми зонт. Он у двери.", "Синий?", "Да, синий."],
     [("What is the weather like?", ["Cold and rainy", "Warm and sunny", "Hot and dry", "Cold and snowy"], "Да, и идёт дождь."), ("Where is the umbrella?", ["By the door", "Under the bed", "On the table", "In the car"], "Он у двери.")]),
    ("Family routine", "Wife and husband", ["Кто сегодня заберёт сына из школы?", "Я заберу. У меня сегодня короткий день.", "Уроки заканчиваются в два.", "Хорошо. Потом пойдём домой.", "Обед в холодильнике.", "Спасибо, я разогрею."],
     [("Who will collect their son?", ["His father", "His mother", "His grandmother", "His aunt"], "Я заберу."), ("When do the lessons end?", ["At two", "At twelve", "At three", "At four"], "Уроки заканчиваются в два.")]),
    ("Cafe", "Customer and server", ["Здравствуйте. Можно чай?", "Чёрный или зелёный?", "Чёрный, пожалуйста, без сахара.", "А что-нибудь поесть?", "Один пирожок с картошкой.", "Хорошо. Садитесь за столик."],
     [("Which drink does the customer order?", ["Black tea", "Green tea", "Black coffee", "Apple juice"], "Чёрный, пожалуйста, без сахара."), ("What filling is in the pastry?", ["Potato", "Apple", "Meat", "Cabbage"], "Один пирожок с картошкой.")]),
    ("Keys", "Wife and husband", ["Ты не видел мои ключи?", "Посмотри на столе.", "Здесь только телефон.", "Тогда в сумке. Ты вчера положила их туда.", "Да, вот они. Спасибо!", "Пожалуйста."],
     [("What is the wife looking for?", ["Her keys", "Her glasses", "Her phone", "Her book"], "Ты не видел мои ключи?"), ("Where does she find them?", ["In her bag", "On the table", "In her coat", "By the window"], "Тогда в сумке.")]),
    ("Library", "Reader and librarian", ["Здравствуйте. Я хочу вернуть эту книгу.", "Пожалуйста, положите её сюда.", "Вы завтра работаете?", "Да, с девяти до шести.", "Спасибо. Я приду утром.", "Будем вас ждать."],
     [("What does the reader want to return?", ["A book", "A ticket", "A newspaper", "A pen"], "Я хочу вернуть эту книгу."), ("When does the library open tomorrow?", ["At nine", "At eight", "At ten", "At eleven"], "Да, с девяти до шести.")]),
    ("Walk", "Two friends", ["Пойдём гулять после работы?", "Давай. Куда пойдём?", "В парк. Там сейчас красиво.", "Хорошо. Возьмём собаку?", "Конечно. Встретимся у моего дома в шесть.", "Договорились."],
     [("Where will the friends go for a walk?", ["To the park", "To the river", "To the beach", "To the square"], "В парк."), ("Which animal will they take?", ["A dog", "A cat", "A rabbit", "A bird"], "Возьмём собаку?")]),
]


def main():
    items = []
    for index, (topic, relationship, lines, questions) in enumerate(DIALOGUES, 1):
        qs = []
        for qi, (stem, answers, evidence) in enumerate(questions):
            offset = (index + qi) % 4
            rotated = answers[-offset:] + answers[:-offset] if offset else answers
            choices = dict(zip("ABCD", rotated))
            qs.append(DraftQuestion(stem_en=stem, choices=choices, correct_key="ABCD"[offset],
                                    rationale_en=f"The dialogue explicitly states: {answers[0]}.", evidence_ru=evidence))
        draft = DialogueDraft(topic=topic, orientation_en=f"Listen to a short conversation. Speakers: {relationship.lower()} (A speaks first).",
                              speakers={"A": "Wife" if relationship == "Wife and husband" else "First speaker",
                                        "B": "Husband" if relationship == "Wife and husband" else "Second speaker"},
                              turns=[Turn(speaker="AB"[i % 2], text=line) for i, line in enumerate(lines)], questions=qs)
        items.append(materialize(draft, f"ru_pilot_{index:02d}", "AI-assisted original draft", "Codex"))
    write_package(ROOT / "data/pilots/russian_0plus_dialogues.json", ContentPackage(items=items))


if __name__ == "__main__":
    main()

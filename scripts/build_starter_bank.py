from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.constants import ILR_THETA, LETTERS
from core.item_bank import shuffle_question
from core.models import AudioAsset, GenerationMetadata, PassageItem, QuestionItem, ValidationReport
from core.validation import content_hash, validate_passage, validate_question
from core.audio import audio_duration_seconds


def q(stem, correct, distractors, rationale, evidence, qtype, level, b):
    return dict(stem=stem, correct=correct, distractors=distractors, rationale=rationale, evidence=evidence, qtype=qtype, level=level, b=b)


READING = [
    dict(id="r001", level="0", b=-2.5, genre="sign", topic="Public information", subtopic="building access",
         orientation="A sign posted at the entrance to a small public office.",
         text="Вход закрыт. Используйте дверь справа.",
         qs=[
             q("What should visitors do?", "Use the door on the right.", ["Wait outside until noon.", "Call the office manager.", "Enter through the left door."], "The sign directs visitors to use a different door on the right.", "Используйте дверь справа", "prominent detail", "0", -2.5),
             q("What is closed?", "The entrance.", ["The entire street.", "The parking area.", "The information desk."], "The first sentence explicitly states that the entrance is closed.", "Вход закрыт", "reference", "0", -2.4),
             q("What is the purpose of the sign?", "To redirect visitors.", ["To advertise a service.", "To announce a meeting.", "To request identification."], "The sign gives a simple instruction about where to enter.", "Используйте дверь справа", "speaker/writer intent", "0", -2.3),
         ]),
    dict(id="r002", level="0+", b=-1.75, genre="message", topic="Daily life", subtopic="pickup change",
         orientation="A short text message from a parent to a family member.",
         text="Я задерживаюсь на работе. Забери, пожалуйста, Машу из школы в четыре часа.",
         qs=[
             q("Why is the writer asking for help?", "The writer will be late at work.", ["The school closes early today.", "Masha has a medical appointment.", "The family car is being repaired."], "The writer says work is causing a delay and then asks for pickup help.", "Я задерживаюсь на работе", "cause and effect", "0+", -1.7),
             q("Who should be picked up?", "Masha.", ["The writer's manager.", "A school teacher.", "A younger brother."], "The message directly names Masha as the person to collect.", "Забери, пожалуйста, Машу", "prominent detail", "0+", -1.8),
             q("When should the pickup happen?", "At four o'clock.", ["At two o'clock.", "At five o'clock.", "After dinner."], "The pickup time is directly stated in the final phrase.", "в четыре часа", "sequence", "0+", -1.6),
             q("What is the writer mainly doing?", "Requesting a favor.", ["Giving travel directions.", "Canceling a school event.", "Complaining about a teacher."], "The message explains a delay and politely asks another person to act.", "Забери, пожалуйста", "speaker/writer intent", "0+", -1.7),
         ]),
    dict(id="r003", level="1", b=-1.0, genre="notice", topic="Public health", subtopic="clinic schedule",
         orientation="A notice posted by a neighborhood clinic.",
         text="В субботу поликлиника работает с девяти утра до двух часов дня. Врачи принимают только по предварительной записи. Аптека на первом этаже будет закрыта из-за ремонта.",
         qs=[
             q("What must patients do before seeing a doctor on Saturday?", "Make an appointment in advance.", ["Buy medicine downstairs.", "Arrive before eight o'clock.", "Bring a repair receipt."], "The notice says doctors see patients only with prior appointments.", "только по предварительной записи", "prominent detail", "1", -1.0),
             q("Why will the pharmacy be closed?", "Because it is being repaired.", ["Because the clinic is moving.", "Because no doctors are working.", "Because medicine has sold out."], "The notice explicitly links the closure to repair work.", "закрыта из-за ремонта", "cause and effect", "1", -0.9),
             q("Which facility is on the first floor?", "The pharmacy.", ["The laboratory.", "The registration desk.", "The emergency room."], "The notice identifies the pharmacy as being on the first floor.", "Аптека на первом этаже", "reference", "1", -1.1),
             q("What is the main purpose of the notice?", "To explain Saturday clinic arrangements.", ["To recruit new medical staff.", "To compare local pharmacies.", "To describe a new treatment."], "All sentences provide practical information about Saturday service conditions.", "В субботу поликлиника работает", "main idea", "1", -0.8),
             q("What happens after two in the afternoon?", "The clinic is no longer open.", ["Doctors begin walk-in visits.", "The pharmacy reopens.", "Repair work stops permanently."], "The stated Saturday hours end at two in the afternoon.", "до двух часов дня", "sequence", "1", -0.9),
         ]),
    dict(id="r004", level="1+", b=-0.25, genre="announcement", topic="Education", subtopic="course registration",
         orientation="An announcement from a community education center.",
         text="Регистрация на вечерние курсы русского языка начнётся 12 августа. В этом году центр откроет две группы: для начинающих и для продолжающих обучение. Количество мест ограничено, поэтому документы советуют подать в течение первой недели. Занятия начнутся в сентябре и будут проходить по вторникам и четвергам.",
         qs=[
             q("Why does the center recommend applying during the first week?", "Because space is limited.", ["Because classes begin immediately.", "Because tuition rises later.", "Because documents expire quickly."], "The announcement connects early application with a limited number of places.", "Количество мест ограничено", "cause and effect", "1+", -0.2),
             q("How are the two groups different?", "They serve different experience levels.", ["They meet in different cities.", "They study different languages.", "They have different tuition prices."], "One group is for beginners and one is for continuing learners.", "для начинающих и для продолжающих обучение", "relationship of ideas", "1+", -0.3),
             q("When will classes begin?", "In September.", ["On August 12.", "During the first week.", "At the end of October."], "Registration begins in August, but the classes themselves begin in September.", "Занятия начнутся в сентябре", "sequence", "1+", -0.4),
         ]),
    dict(id="r005", level="2", b=0.5, genre="news report", topic="Economics", subtopic="regional transport",
         orientation="A brief regional news report about public transportation.",
         text="Городская администрация объявила, что с октября на трёх автобусных маршрутах появятся дополнительные вечерние рейсы. Решение приняли после многочисленных обращений жителей новых районов, которым трудно возвращаться домой после поздних смен. По данным транспортного управления, в течение первых двух месяцев специалисты будут изучать пассажиропоток. Если новые рейсы окажутся востребованными, расписание сохранят и после завершения испытательного периода.",
         qs=[
             q("What prompted the city to add evening service?", "Complaints from residents of new neighborhoods.", ["A reduction in fuel prices.", "A request from tourist agencies.", "Construction near the central station."], "The report says the decision followed many appeals from residents who work late.", "после многочисленных обращений жителей новых районов", "cause and effect", "2", 0.5),
             q("What will officials examine during the first two months?", "How many passengers use the new trips.", ["Whether drivers prefer new uniforms.", "How much road construction costs.", "Whether residents move closer to work."], "The transport authority will study passenger flow during the trial.", "будут изучать пассажиропоток", "prominent detail", "2", 0.4),
             q("Under what condition will the schedule continue?", "If the added trips attract sufficient use.", ["If all routes become free.", "If the city buys electric buses.", "If late shifts are eliminated."], "Continuation depends on whether the new service proves demanded.", "Если новые рейсы окажутся востребованными", "inference", "2", 0.6),
             q("What is the function of the two-month period?", "It is a trial used to evaluate demand.", ["It is a deadline for resident complaints.", "It is a holiday transportation schedule.", "It is a driver training course."], "The period is described as an испытательный период during which passenger use is measured.", "испытательного периода", "meaning from context", "2", 0.6),
         ]),
    dict(id="r006", level="2+", b=1.25, genre="commentary", topic="Technology", subtopic="digital services",
         orientation="A newspaper commentary on moving municipal services online.",
         text="Перевод муниципальных услуг в электронный формат обычно представляют как очевидный шаг к удобству. Действительно, заявление можно подать из дома, а статус обращения — проверить без очереди. Однако для части пожилых жителей цифровизация создаёт новый барьер: им приходится осваивать сложные интерфейсы или просить помощи у родственников. Поэтому отказ от обычных приёмных был бы преждевременным. Более разумной выглядит переходная модель, при которой электронные сервисы развиваются, но граждане сохраняют возможность лично обратиться к специалисту.",
         qs=[
             q("What is the author's main position?", "Digital services should expand without eliminating in-person help.", ["All municipal offices should close immediately.", "Older residents should rely on relatives.", "Online applications should be limited to businesses."], "The author supports a transition model that preserves personal access while digital services grow.", "электронные сервисы развиваются, но граждане сохраняют возможность лично обратиться", "main idea", "2+", 1.2),
             q("Why does the author call eliminating ordinary offices premature?", "Some residents still face difficulty using digital systems.", ["Online systems are always more expensive.", "Municipal workers oppose every reform.", "Relatives refuse to help older people."], "The concern is that digitalization creates a barrier for some older residents.", "для части пожилых жителей цифровизация создаёт новый барьер", "cause and effect", "2+", 1.2),
             q("What attitude does the author show toward digitalization?", "Qualified support.", ["Complete rejection.", "Unquestioning enthusiasm.", "Indifference to the outcome."], "The author acknowledges convenience but also emphasizes access problems and a gradual solution.", "Однако для части пожилых жителей", "tone or attitude", "2+", 1.3),
             q("What does 'переходная модель' imply in this context?", "A temporary mixed system with online and in-person options.", ["A permanent ban on digital services.", "A transfer of services to private companies.", "A program available only during elections."], "The following clause defines the model as simultaneous digital development and continued personal access.", "электронные сервисы развиваются, но граждане сохраняют возможность", "meaning from context", "2+", 1.4),
             q("How are the first and second halves of the commentary related?", "The second qualifies the benefits described in the first.", ["The second repeats the same benefits with examples.", "The second changes to an unrelated financial issue.", "The second proves that no residents use online services."], "The text first presents convenience and then introduces limitations that require a balanced policy.", "Однако для части пожилых жителей", "relationship of ideas", "2+", 1.4),
         ]),
    dict(id="r007", level="3", b=2.0, genre="policy analysis", topic="International relations", subtopic="regional cooperation",
         orientation="An analytical excerpt about cooperation among neighboring states.",
         text="Региональные соглашения нередко оценивают по числу подписанных документов, хотя формальное расширение сотрудничества ещё не означает его устойчивости. Государства могут быстро согласовать декларацию, если она не требует значительных внутренних изменений. Гораздо сложнее поддерживать совместные механизмы, когда экономические интересы расходятся или меняется политическое руководство. Именно поэтому эффективность союза проявляется не в период торжественных саммитов, а во время кризиса, когда участникам приходится выбирать между краткосрочной выгодой и ранее принятыми обязательствами. Если институты способны пережить такой конфликт интересов, сотрудничество получает собственную логику и перестаёт полностью зависеть от личных отношений лидеров.",
         qs=[
             q("What criterion does the author consider most revealing of durable cooperation?", "Whether institutions survive conflicts of interest during crises.", ["How many declarations leaders sign at summits.", "Whether all leaders have close personal relations.", "How quickly states expand membership."], "The author argues that effectiveness is demonstrated during crisis and by institutions surviving conflicting interests.", "Если институты способны пережить такой конфликт интересов", "main idea", "3", 2.0),
             q("Why are declarations relatively easy to agree on?", "They may require little domestic change.", ["They automatically resolve economic disputes.", "They are written by private companies.", "They prevent changes in political leadership."], "The text says declarations can be agreed quickly when they demand no major internal changes.", "если она не требует значительных внутренних изменений", "cause and effect", "3", 1.9),
             q("What contrast structures the analysis?", "Ceremonial agreement versus institutional performance under pressure.", ["Economic growth versus population decline.", "Regional trade versus global tourism.", "Personal friendship versus cultural exchange."], "The author contrasts formal documents and summits with difficult crisis choices and institutional endurance.", "не в период торжественных саммитов, а во время кризиса", "relationship of ideas", "3", 2.1),
         ]),
    dict(id="r008", level="1", b=-0.9, genre="public announcement", topic="Accidents and disasters", subtopic="storm closure",
         orientation="A municipal announcement after severe weather.",
         text="Из-за сильного ветра городской парк сегодня закрыт. Сотрудники проверяют деревья и убирают упавшие ветки. Детскую площадку планируют открыть завтра утром, но спортивная зона останется закрытой до пятницы.",
         qs=[
             q("Why is the park closed today?", "Because of strong wind.", ["Because of a public festival.", "Because workers are painting benches.", "Because a sports event is underway."], "The opening phrase directly gives strong wind as the reason.", "Из-за сильного ветра", "cause and effect", "1", -1.0),
             q("What are employees doing?", "Checking trees and removing fallen branches.", ["Building a new playground.", "Selling tickets at the gate.", "Moving sports equipment indoors."], "The announcement lists both tree inspection and branch removal.", "проверяют деревья и убирают упавшие ветки", "prominent detail", "1", -0.9),
             q("Which area is expected to open first?", "The children's playground.", ["The sports zone.", "The entire park.", "The parking garage."], "The playground is planned for tomorrow, while the sports zone stays closed until Friday.", "Детскую площадку планируют открыть завтра утром", "sequence", "1", -0.8),
             q("What is the announcement mainly about?", "A temporary closure and reopening schedule.", ["A new park construction project.", "A competition between sports teams.", "A request for volunteer gardeners."], "The notice explains why areas are closed and when they may reopen.", "останется закрытой до пятницы", "main idea", "1", -0.8),
         ]),
    dict(id="r009", level="1+", b=-0.2, genre="email", topic="Workplace", subtopic="meeting change",
         orientation="An email from a department supervisor to employees.",
         text="Коллеги, завтрашнее совещание переносится с десяти на одиннадцать часов, потому что директор будет участвовать в видеоконференции. Повестка остаётся прежней: результаты квартала и план работы на август. Пожалуйста, пришлите свои отчёты до конца сегодняшнего дня, чтобы я успел включить данные в общую презентацию.",
         qs=[
             q("Why was the meeting moved?", "The director has a video conference.", ["The quarterly results are incomplete.", "The office closes at ten.", "Employees requested a later date."], "The supervisor explicitly connects the time change to the director's video conference.", "потому что директор будет участвовать в видеоконференции", "cause and effect", "1+", -0.2),
             q("What remains unchanged?", "The meeting agenda.", ["The meeting time.", "The report deadline.", "The presentation format."], "The email states that the agenda remains the same.", "Повестка остаётся прежней", "prominent detail", "1+", -0.3),
             q("Why should reports be sent today?", "So their data can be added to the shared presentation.", ["So the director can cancel the meeting.", "So employees can leave early tomorrow.", "So August plans can be removed."], "The supervisor needs time to include the data in the combined presentation.", "чтобы я успел включить данные в общую презентацию", "speaker/writer intent", "1+", -0.1),
             q("What two topics will the meeting cover?", "Quarterly results and the August work plan.", ["Hiring and office repairs.", "Video equipment and travel.", "Training and annual leave."], "The agenda lists the quarterly results and the August work plan.", "результаты квартала и план работы на август", "prominent detail", "1+", -0.2),
             q("What should employees do first?", "Submit their reports by the end of today.", ["Join the video conference.", "Rewrite the meeting agenda.", "Prepare a separate August meeting."], "The only requested employee action before the meeting is sending reports today.", "пришлите свои отчёты до конца сегодняшнего дня", "sequence", "1+", -0.1),
         ]),
    dict(id="r010", level="2", b=0.6, genre="report", topic="Crime and law enforcement", subtopic="fraud prevention",
         orientation="A public report summarizing a police fraud-prevention campaign.",
         text="Полиция области сообщила о снижении числа телефонных мошенничеств среди пожилых жителей. За последние три месяца сотрудники провели встречи в социальных центрах и объяснили, как распознавать звонки от людей, выдающих себя за банковских работников. Одновременно банки начали автоматически предупреждать клиентов о подозрительных переводах. В полиции считают, что результат связан именно с сочетанием личных консультаций и технических мер, а не с одной отдельной инициативой.",
         qs=[
             q("What result did the regional police report?", "Fewer telephone fraud cases among older residents.", ["More bank branches in rural areas.", "A rise in suspicious transfers.", "Fewer meetings at social centers."], "The report directly states a decline in telephone fraud among elderly residents.", "снижении числа телефонных мошенничеств среди пожилых жителей", "prominent detail", "2", 0.5),
             q("What did police explain during the meetings?", "How to identify callers pretending to be bank employees.", ["How to open a new bank account.", "How to request a police pension.", "How to repair a mobile phone."], "The meetings focused on recognizing impersonation by supposed bank workers.", "как распознавать звонки от людей, выдающих себя за банковских работников", "prominent detail", "2", 0.5),
             q("How do police interpret the improvement?", "It resulted from combining education and technical safeguards.", ["It came entirely from one new law.", "It happened because residents stopped using banks.", "It was caused only by police arrests."], "Police attribute the result to the combination of consultations and technical measures.", "сочетанием личных консультаций и технических мер", "relationship of ideas", "2", 0.7),
         ]),
    dict(id="r011", level="2+", b=1.3, genre="essay", topic="Culture and society", subtopic="museum access",
         orientation="An essay discussing how museums define public access.",
         text="Бесплатный вход часто называют главным условием доступности музея. Но отсутствие платы не гарантирует, что посетитель действительно сможет воспользоваться культурным пространством. Если экспозиция не имеет понятных пояснений, здание неудобно для людей с ограниченной мобильностью, а часы работы совпадают с рабочим днём большинства горожан, формальная бесплатность мало что меняет. Доступность следует понимать шире: как сочетание цены, физической среды, языка экспозиции и расписания. Такой подход требует больше ресурсов, зато позволяет оценивать музей не по числу открытых дверей, а по тому, кто реально может в них войти и получить содержательный опыт.",
         qs=[
             q("What assumption does the author challenge?", "That free admission alone makes a museum accessible.", ["That museums should display historical objects.", "That visitors prefer weekend hours.", "That cultural spaces require public funding."], "The opening contrasts free entry with the broader conditions needed for genuine access.", "отсутствие платы не гарантирует", "main idea", "2+", 1.2),
             q("How does the author redefine accessibility?", "As a combination of price, environment, language, and schedule.", ["As the total number of objects on display.", "As a museum's distance from the city center.", "As the popularity of its advertising."], "The essay explicitly lists four interacting dimensions of accessibility.", "сочетание цены, физической среды, языка экспозиции и расписания", "prominent detail", "2+", 1.2),
             q("What does 'формальная бесплатность' imply?", "A nominal benefit that may not produce real access.", ["A temporary discount for formal events.", "A legal ban on charging admission.", "A membership program for employees."], "The phrase contrasts free entry in name with practical barriers that remain.", "формальная бесплатность мало что меняет", "meaning from context", "2+", 1.4),
             q("What standard does the author prefer for evaluating a museum?", "Who can actually enter and gain a meaningful experience.", ["How many doors the building has.", "How expensive the collection is.", "How often admission prices change."], "The conclusion shifts evaluation from open doors to actual participation and meaningful experience.", "кто реально может в них войти и получить содержательный опыт", "speaker/writer intent", "2+", 1.4),
         ]),
    dict(id="r012", level="3", b=2.1, genre="analytical commentary", topic="Science and technology", subtopic="automation policy",
         orientation="An analytical commentary on measuring the effects of workplace automation.",
         text="Дискуссия об автоматизации труда часто сводится к вопросу о том, сколько рабочих мест исчезнет. Такая постановка удобна для громких прогнозов, но плохо описывает реальные изменения. Технологии нередко не уничтожают профессию целиком, а перераспределяют внутри неё задачи: рутинные операции переходят к системе, тогда как от человека требуется больше контроля, интерпретации и общения. В результате статистика занятости может выглядеть стабильной, хотя содержание работы и требования к квалификации существенно меняются. Политика, ориентированная только на число сохранённых должностей, рискует пропустить именно эту трансформацию. Поэтому оценивать последствия автоматизации следует одновременно по занятости, структуре задач и доступности переобучения.",
         qs=[
             q("What limitation does the author identify in common automation forecasts?", "They focus on job counts and miss changes within occupations.", ["They rely too heavily on employee interviews.", "They assume technology never affects qualifications.", "They measure training costs instead of employment."], "The commentary argues that jobs may remain while their internal task structure changes significantly.", "не уничтожают профессию целиком, а перераспределяют внутри неё задачи", "main idea", "3", 2.0),
             q("Why can employment statistics be misleading?", "Stable job numbers can hide major changes in work content.", ["Companies stop reporting employee numbers.", "Automated systems create only temporary jobs.", "Workers routinely change their job titles."], "The text states that employment may look stable even as duties and qualification demands change.", "статистика занятости может выглядеть стабильной, хотя содержание работы", "inference", "3", 2.1),
             q("What policy risk does the author emphasize?", "Protecting positions without addressing changing skill demands.", ["Funding too many communication technologies.", "Reducing the number of routine operations.", "Collecting information from several indicators."], "A policy focused only on preserved posts may overlook transformation and retraining needs.", "рискует пропустить именно эту трансформацию", "speaker/writer intent", "3", 2.2),
             q("How does the final sentence relate to the preceding argument?", "It proposes a multi-dimensional evaluation based on the identified problem.", ["It rejects the earlier discussion as irrelevant.", "It supplies a historical example of automation.", "It narrows the analysis back to job counts alone."], "The conclusion responds to the earlier limitation by adding tasks and retraining to employment measures.", "одновременно по занятости, структуре задач и доступности переобучения", "relationship of ideas", "3", 2.2),
             q("What attitude does the author display toward automation itself?", "Analytical caution rather than simple support or opposition.", ["Unqualified enthusiasm for replacing workers.", "Complete rejection of workplace technology.", "Indifference to worker qualifications."], "The author does not condemn technology, but warns against simplistic measurement and policy.", "Такая постановка удобна для громких прогнозов, но плохо описывает реальные изменения", "tone or attitude", "3", 2.1),
         ]),
]

LISTENING = [
    dict(id="l001", level="0", b=-2.5, genre="station announcement", topic="Transportation", subtopic="platform change", orientation="A brief announcement at a train station.", text="Поезд в Москву отправится со второй платформы.", qs=[
        q("Where will the Moscow train depart from?", "Platform two.", ["Platform one.", "Platform three.", "The bus terminal."], "The announcement directly names the second platform.", "со второй платформы", "prominent detail", "0", -2.5),
        q("What is the announcement about?", "A train departure location.", ["A delayed flight.", "A ticket refund.", "A station closure."], "The message identifies where a train will depart.", "Поезд в Москву отправится", "main idea", "0", -2.4),
    ]),
    dict(id="l002", level="0+", b=-1.8, genre="voicemail", topic="Daily life", subtopic="late arrival", orientation="A short voicemail from a friend.", text="Привет, я буду дома после семи. Начинай ужин без меня.", qs=[
        q("When will the speaker be home?", "After seven.", ["Before five.", "At noon.", "Tomorrow morning."], "The speaker directly says the arrival will be after seven.", "буду дома после семи", "prominent detail", "0+", -1.8),
        q("What should the listener do?", "Start dinner without the speaker.", ["Wait at the bus stop.", "Cancel tomorrow's plans.", "Call the restaurant manager."], "The speaker tells the listener to begin dinner without waiting.", "Начинай ужин без меня", "speaker/writer intent", "0+", -1.7),
        q("Why is the message likely being sent?", "To explain a late arrival and adjust dinner plans.", ["To invite the listener to breakfast.", "To report a broken appliance.", "To ask for directions home."], "The two sentences connect a late arrival with a request not to wait for dinner.", "после семи. Начинай ужин без меня", "cause and effect", "0+", -1.6),
    ]),
    dict(id="l003", level="1", b=-1.0, genre="store announcement", topic="Commerce", subtopic="closing time", orientation="An announcement in a grocery store.", text="Уважаемые покупатели, магазин закроется через пятнадцать минут. Просим пройти к кассам и завершить покупки.", qs=[
        q("What will happen in fifteen minutes?", "The store will close.", ["The cash registers will open.", "A sale will begin.", "The lights will be repaired."], "The announcement explicitly states the store's closing time.", "магазин закроется через пятнадцать минут", "sequence", "1", -1.0),
        q("What are customers asked to do?", "Go to the registers and finish shopping.", ["Return all products to shelves.", "Leave their bags at the entrance.", "Wait for a manager near the door."], "Customers are asked to proceed to checkout and complete purchases.", "пройти к кассам и завершить покупки", "speaker/writer intent", "1", -0.9),
        q("What is the main purpose of the message?", "To prepare customers for closing.", ["To advertise a new product.", "To explain a price increase.", "To announce a lost item."], "The message gives a closing warning and a final action for customers.", "магазин закроется", "main idea", "1", -0.9),
    ]),
    dict(id="l004", level="1+", b=-0.3, genre="telephone message", topic="Public health", subtopic="appointment change", orientation="A clinic employee leaves a message for a patient.", text="Добрый день, это городская стоматология. Ваш приём в среду переносится с трёх часов на половину пятого, потому что врач будет на срочной операции. Если новое время вам не подходит, позвоните нам до конца дня.", qs=[
        q("Why was the appointment moved?", "The dentist has an urgent operation.", ["The patient requested a later time.", "The clinic is closing for repairs.", "The receptionist entered the wrong date."], "The employee explicitly gives an urgent operation as the reason.", "потому что врач будет на срочной операции", "cause and effect", "1+", -0.2),
        q("What should the patient do if the new time is inconvenient?", "Call the clinic by the end of the day.", ["Arrive at the original time anyway.", "Send a letter next week.", "Visit another clinic immediately."], "The final sentence gives a call deadline for changing the new time.", "позвоните нам до конца дня", "speaker/writer intent", "1+", -0.3),
    ]),
    dict(id="l005", level="2", b=0.5, genre="radio news", topic="Environment", subtopic="river cleanup", orientation="A short local radio news report.", text="В выходные более двухсот добровольцев участвовали в очистке берега реки. За два дня они собрали около трёх тонн мусора. Организаторы отметили, что в этом году к акции впервые присоединились несколько местных предприятий, которые предоставили транспорт и защитное оборудование. Следующую уборку планируют провести в начале осени.", qs=[
        q("What was new about this year's cleanup?", "Local businesses participated for the first time.", ["The event lasted an entire month.", "Only professional workers were allowed.", "The cleanup moved away from the river."], "The report says several local businesses joined the campaign for the first time.", "впервые присоединились несколько местных предприятий", "prominent detail", "2", 0.5),
        q("How did the businesses support the event?", "They provided transportation and protective equipment.", ["They paid residents to stay home.", "They built a new bridge.", "They organized a music festival."], "The report specifies transportation and protective equipment as business contributions.", "предоставили транспорт и защитное оборудование", "prominent detail", "2", 0.4),
        q("What is planned next?", "Another cleanup in early autumn.", ["A permanent closure of the riverbank.", "A cleanup every evening.", "A business conference next week."], "The final sentence schedules the next cleanup for the beginning of autumn.", "Следующую уборку планируют провести в начале осени", "sequence", "2", 0.5),
    ]),
    dict(id="l006", level="2+", b=1.3, genre="interview excerpt", topic="Education", subtopic="remote learning", orientation="An excerpt from a radio interview with a school principal.", text="Когда мы впервые ввели дистанционные занятия, многие считали их временной заменой обычных уроков. Но постепенно стало ясно, что некоторые элементы полезно сохранить. Например, ученики, которые долго болеют, могут подключаться к консультациям, а родители — смотреть записи общих собраний. При этом полностью переходить в онлайн мы не собираемся: живое общение остаётся основой школьной жизни.", qs=[
        q("How did the principal's view of remote tools change?", "Some features proved useful beyond the temporary emergency.", ["All online tools were judged ineffective.", "Remote classes became the school's only format.", "Parents asked the school to remove recordings."], "The speaker says remote learning began as temporary but some elements should remain.", "некоторые элементы полезно сохранить", "relationship of ideas", "2+", 1.2),
        q("What boundary does the principal set?", "The school will not move completely online.", ["Students may never join consultations remotely.", "Parents may not watch meeting recordings.", "Teachers must cancel in-person lessons during illness."], "The speaker explicitly rejects a complete online transition.", "полностью переходить в онлайн мы не собираемся", "speaker/writer intent", "2+", 1.3),
        q("What attitude toward remote learning is expressed?", "Selective and pragmatic acceptance.", ["Total enthusiasm for replacing school buildings.", "Complete hostility toward any technology.", "Uncertainty about whether schools need teachers."], "The speaker preserves useful tools while defending live interaction as foundational.", "При этом полностью переходить в онлайн мы не собираемся: живое общение остаётся основой школьной жизни", "tone or attitude", "2+", 1.4),
    ]),
    dict(id="l007", level="3", b=2.0, genre="policy discussion", topic="Economics", subtopic="regional investment", orientation="A policy expert comments on regional investment incentives.", text="Налоговые льготы могут привлечь предприятие в регион, но сами по себе они редко создают долгосрочное развитие. Если компании не находят подготовленных работников, надёжной инфраструктуры и понятных правил, они либо сокращают проект, либо уходят после окончания льготного периода. Поэтому конкуренция регионов только по размеру скидки превращается в дорогую гонку. Более устойчивый результат возникает, когда льготы являются частью общей стратегии, а не заменяют её.", qs=[
        q("What is the expert's central argument?", "Tax incentives work best as one part of a broader development strategy.", ["Regions should eliminate all investment incentives.", "Companies choose locations only by tax rates.", "Infrastructure matters only after incentives expire."], "The conclusion says incentives should form part of an overall strategy rather than substitute for it.", "льготы являются частью общей стратегии, а не заменяют её", "main idea", "3", 2.0),
        q("Why can competition based only on tax discounts become costly?", "Regions may spend heavily without creating conditions that keep firms.", ["Companies are legally required to reject discounts.", "Workers always move away from low-tax regions.", "Infrastructure automatically becomes cheaper."], "The speaker links weak fundamentals to firms reducing or leaving projects after incentives end.", "уходят после окончания льготного периода", "inference", "3", 2.1),
    ]),
    dict(id="l008", level="1", b=-0.9, genre="weather advisory", topic="Accidents and disasters", subtopic="road conditions", orientation="A morning weather advisory for drivers.", text="Ночью температура опустилась ниже нуля, поэтому на дорогах возможен лёд. Водителей просят снизить скорость и соблюдать дистанцию. После полудня ожидается потепление.", qs=[
        q("What danger is mentioned?", "Ice may form on the roads.", ["Heavy fog will close airports.", "Flooding will block the highway.", "Strong wind will damage bridges."], "The advisory warns that road ice is possible after freezing temperatures.", "на дорогах возможен лёд", "prominent detail", "1", -1.0),
        q("What are drivers asked to do?", "Slow down and keep distance.", ["Use only public transportation.", "Stop driving until tomorrow.", "Turn on emergency sirens."], "The advisory gives both speed and following-distance instructions.", "снизить скорость и соблюдать дистанцию", "speaker/writer intent", "1", -0.9),
        q("What change is expected later?", "Warmer weather after noon.", ["Snow before sunrise.", "Stronger wind at night.", "Colder weather all day."], "The final sentence predicts warming after midday.", "После полудня ожидается потепление", "sequence", "1", -0.8),
    ]),
    dict(id="l009", level="1+", b=-0.2, genre="workplace briefing", topic="Workplace", subtopic="equipment maintenance", orientation="A supervisor gives a short morning briefing.", text="Сегодня после обеда специалисты будут проверять систему вентиляции на втором этаже. Работа займёт примерно два часа. Сотрудникам отдела продаж нужно до часа дня перенести важные встречи в переговорную на первом этаже. Остальные кабинеты продолжат работать как обычно.", qs=[
        q("Who must move important meetings?", "Employees in the sales department.", ["All building visitors.", "The maintenance specialists.", "Employees on the first floor."], "The briefing specifically names sales department employees.", "Сотрудникам отдела продаж", "reference", "1+", -0.2),
        q("Why are meetings being moved?", "Ventilation will be inspected on the second floor.", ["The first-floor room is being painted.", "The sales department is closing permanently.", "A company celebration begins at noon."], "The action is required because specialists will inspect ventilation on the second floor.", "проверять систему вентиляции на втором этаже", "cause and effect", "1+", -0.1),
        q("What remains normal?", "Work in the other offices.", ["All meetings on the second floor.", "The ventilation inspection schedule.", "The sales department's meeting rooms."], "The final sentence says the remaining offices continue as usual.", "Остальные кабинеты продолжат работать как обычно", "prominent detail", "1+", -0.2),
    ]),
    dict(id="l010", level="2", b=0.6, genre="news report", topic="Science and technology", subtopic="medical system", orientation="A news report about a hospital's new scheduling system.", text="Областная больница начала использовать электронную систему распределения операций. Программа учитывает срочность случая, наличие специалистов и свободные места в палатах. Руководство ожидает, что это сократит число отмен в последний момент. Однако врачи подчёркивают, что окончательное решение всё равно принимает медицинская команда, особенно когда состояние пациента быстро меняется.", qs=[
        q("What problem is the new system expected to reduce?", "Last-minute operation cancellations.", ["The number of medical specialists.", "The size of hospital wards.", "Changes in patient conditions."], "Hospital leadership expects fewer cancellations at the last moment.", "сократит число отмен в последний момент", "cause and effect", "2", 0.5),
        q("What limits the program's authority?", "The medical team still makes the final decision.", ["Patients select all surgery times themselves.", "The system works only outside the hospital.", "Ward availability is never considered."], "Doctors emphasize that the final decision remains with the medical team.", "окончательное решение всё равно принимает медицинская команда", "relationship of ideas", "2", 0.7),
        q("Which factor does the program consider?", "The urgency of the case.", ["The patient's preferred television channel.", "The age of the hospital building.", "The cost of public transportation."], "Urgency is the first scheduling factor listed in the report.", "учитывает срочность случая", "prominent detail", "2", 0.5),
    ]),
    dict(id="l011", level="2+", b=1.2, genre="public affairs interview", topic="Government and politics", subtopic="public consultation", orientation="A city official discusses a public consultation process.", text="Мы получили почти тысячу предложений по проекту новой площади, но количество ответов ещё не означает, что обсуждение было представительным. Большинство комментариев поступило через интернет, тогда как пожилые жители и владельцы небольших магазинов участвовали заметно реже. Поэтому перед окончательным решением мы проведём очные встречи в нескольких районах. Наша задача — не просто собрать больше мнений, а понять, чьи интересы пока остались незамеченными.", qs=[
        q("Why is the official not satisfied with the large number of responses?", "Some affected groups participated much less than others.", ["Most comments opposed building any square.", "Internet comments cannot be read by officials.", "The city received fewer than ten proposals."], "The official notes low participation by older residents and small shop owners.", "участвовали заметно реже", "inference", "2+", 1.2),
        q("What is the purpose of the planned in-person meetings?", "To reach interests underrepresented in the online response.", ["To replace every submitted online comment.", "To announce the final design immediately.", "To recruit workers for construction."], "The official wants to identify whose interests have not yet been noticed.", "чьи интересы пока остались незамеченными", "speaker/writer intent", "2+", 1.3),
    ]),
    dict(id="l012", level="3", b=2.1, genre="analytical interview", topic="International relations", subtopic="sanctions policy", orientation="An analyst discusses how governments evaluate sanctions.", text="Эффект санкций трудно измерять по одному показателю. Сокращение торговли может свидетельствовать о давлении, но одновременно компании перестраивают цепочки поставок, а государство перераспределяет расходы. Кроме того, политическая цель санкций может отличаться от экономического ущерба: меры способны повысить цену определённого решения, не заставив руководство немедленно изменить курс. Поэтому серьёзная оценка должна различать прямые потери, адаптацию и политическое поведение, а также учитывать время, за которое проявляются последствия.", qs=[
        q("Why does the analyst reject using a single indicator?", "Economic adaptation and political outcomes can move differently.", ["Trade data are never available to governments.", "Sanctions produce no direct economic losses.", "Political leaders immediately change policy."], "The analyst distinguishes trade pressure, adaptation, economic harm, and political behavior.", "политическая цель санкций может отличаться от экономического ущерба", "relationship of ideas", "3", 2.1),
        q("What does the analyst imply about timing?", "Some consequences may emerge only after a delay.", ["All sanctions end within one week.", "Trade always recovers immediately.", "Political effects appear before measures begin."], "The final phrase says evaluation must account for the time in which consequences appear.", "учитывать время, за которое проявляются последствия", "inference", "3", 2.0),
        q("What is the speaker's main recommendation?", "Evaluate direct losses, adaptation, and political behavior separately.", ["Judge sanctions only by trade volume.", "Ignore the stated political objective.", "Measure only government spending."], "The final sentence explicitly lists the dimensions a serious assessment should distinguish.", "различать прямые потери, адаптацию и политическое поведение", "main idea", "3", 2.1),
    ]),
    dict(id="l013", level="1", b=-0.8, genre="school announcement", topic="Education", subtopic="sports day", orientation="A school announcement about an event schedule.", text="Спортивный праздник начнётся в десять часов на школьном стадионе. Ученикам нужно прийти на полчаса раньше и принести воду. Если будет сильный дождь, мероприятие перенесут в спортивный зал.", qs=[
        q("When should students arrive?", "At nine thirty.", ["At ten thirty.", "At eleven o'clock.", "After the event begins."], "Students are told to arrive half an hour before the ten o'clock start.", "прийти на полчаса раньше", "sequence", "1", -0.7),
        q("What should students bring?", "Water.", ["A musical instrument.", "A school computer.", "A lunch ticket."], "The announcement directly tells students to bring water.", "принести воду", "prominent detail", "1", -0.9),
        q("What happens if there is heavy rain?", "The event moves to the gym.", ["The event is canceled permanently.", "Students go to the stadium later.", "The school closes for a week."], "Heavy rain triggers a change from the stadium to the sports hall.", "перенесут в спортивный зал", "cause and effect", "1", -0.8),
    ]),
    dict(id="l014", level="2", b=0.4, genre="consumer report", topic="Commerce", subtopic="delivery service", orientation="A consumer report about a grocery delivery pilot.", text="Сеть магазинов завершила трёхмесячный эксперимент с доставкой продуктов в отдалённые посёлки. Заказы принимали два раза в неделю через мобильное приложение и по телефону. Компания сообщила, что телефонной линией пользовались чаще, чем ожидалось, особенно жители старшего возраста. Поэтому при расширении услуги приложение сохранят, но число операторов увеличат.", qs=[
        q("What surprised the company?", "Telephone ordering was more popular than expected.", ["No customers used the delivery service.", "The mobile application failed completely.", "Deliveries occurred every day."], "The report says the phone line was used more often than expected.", "телефонной линией пользовались чаще, чем ожидалось", "prominent detail", "2", 0.4),
        q("How will the service change when it expands?", "The company will add more telephone operators.", ["It will eliminate telephone orders.", "It will serve only younger customers.", "It will stop using the mobile application."], "The company will keep the app but increase the number of operators.", "число операторов увеличат", "cause and effect", "2", 0.5),
    ]),
    dict(id="l015", level="2+", b=1.4, genre="commentary", topic="Culture and society", subtopic="public libraries", orientation="A commentator discusses the changing role of public libraries.", text="Когда электронные книги стали широко доступны, некоторые предсказывали, что библиотеки потеряют смысл. Но библиотека выполняет не только функцию хранения текстов. Для школьников это место для самостоятельной работы, для пожилых людей — доступ к цифровым услугам, а для местных организаций — пространство встреч. Поэтому сокращение числа выданных печатных книг не обязательно означает снижение общественной ценности библиотеки; возможно, меняется сам способ, которым жители ею пользуются.", qs=[
        q("What earlier prediction does the commentator question?", "That electronic books would make libraries unnecessary.", ["That schools would stop assigning independent work.", "That older people would reject all digital services.", "That local organizations would build private offices."], "The opening recalls predictions that libraries would lose their purpose after e-books spread.", "библиотеки потеряют смысл", "main idea", "2+", 1.3),
        q("Why may fewer printed-book loans be a misleading indicator?", "People may be using libraries for other valuable functions.", ["Printed books are no longer counted by libraries.", "Residents are required to buy every book.", "Digital services are available only to staff."], "The speaker lists study, digital access, and meeting space as other forms of use.", "меняется сам способ, которым жители ею пользуются", "inference", "2+", 1.4),
        q("What is the commentator's attitude toward the library's future?", "Cautiously optimistic about adaptation.", ["Certain that libraries have no value.", "Angry that electronic books exist.", "Uninterested in community services."], "The commentary rejects a simple decline narrative and emphasizes changing community functions.", "не обязательно означает снижение общественной ценности", "tone or attitude", "2+", 1.4),
    ]),
]


def place_correct(question: QuestionItem, target_key: str, seed_base: str) -> QuestionItem:
    for i in range(1000):
        candidate = shuffle_question(question, random.Random(f"{seed_base}:{i}"))
        if candidate.correct_key == target_key:
            return candidate
    raise RuntimeError("Could not place correct key")


def make_records():
    records = []
    reports = []
    position_index = 0
    for skill, specs in (("reading", READING), ("listening", LISTENING)):
        for spec in specs:
            passage_id = spec["id"]
            question_ids = [f"{passage_id}_q{i+1}" for i in range(len(spec["qs"]))]
            audio_id = f"a_{passage_id}" if skill == "listening" else None
            p = PassageItem(
                id=passage_id,
                skill=skill,
                target_ilr=spec["level"],
                provisional_difficulty=spec["b"],
                genre=spec["genre"],
                topic=spec["topic"],
                subtopic=spec["subtopic"],
                orientation_en=spec["orientation"],
                passage_ru=spec["text"],
                source_type="synthetic",
                provenance={"author": "project starter-bank team", "method": "human-authored synthetic practice content"},
                license="Project-authored synthetic content; MIT repository license",
                word_count=len(spec["text"].split()),
                segment_count=max(1, len([x for x in spec["text"].split(".") if x.strip()])),
                vocabulary_metadata={"provisional_ilr": spec["level"]},
                discourse_metadata={"genre": spec["genre"], "complexity_basis": "discourse and reasoning demand, not length alone"},
                question_ids=question_ids,
                audio_asset_id=audio_id,
                voice_metadata={"voice": "eSpeak Russian male", "synthetic": True} if skill == "listening" else {},
                generation=GenerationMetadata(provider="manual", model="human-authored", prompt_version="starter-bank-v1"),
                validation_status="accepted",
                content_hash=content_hash(spec["text"]),
                duplicate_detection_hash=content_hash(spec["text"]),
            )
            question_models = []
            for idx, raw in enumerate(spec["qs"]):
                base_choices = {"A": raw["correct"], "B": raw["distractors"][0], "C": raw["distractors"][1], "D": raw["distractors"][2]}
                base = QuestionItem(
                    id=question_ids[idx], passage_id=passage_id, stem_en=raw["stem"], choices=base_choices,
                    correct_key="A", rationale_en=raw["rationale"], evidence_ru=raw["evidence"],
                    question_type=raw["qtype"], target_ilr=raw["level"], provisional_difficulty=raw["b"],
                    generation=GenerationMetadata(provider="manual", model="human-authored", prompt_version="starter-bank-v1"),
                    validation_status="accepted",
                )
                target = LETTERS[position_index % 4]
                position_index += 1
                model = place_correct(base, target, base.id)
                question_models.append(model)
            p_report = validate_passage(p, question_models)
            p.validation_report_id = p_report.id
            if p_report.status != "accepted":
                raise RuntimeError(f"Passage failed: {p.id} {p_report.failure_reasons}")
            records.append({"kind": "passage", "data": p.model_dump(mode="json")})
            reports.append({"kind": "validation", "data": p_report.model_dump(mode="json")})
            for model in question_models:
                report = validate_question(model, p)
                model.validation_report_id = report.id
                if report.status != "accepted":
                    raise RuntimeError(f"Question failed: {model.id} {report.failure_reasons} {report.ambiguity_flags}")
                records.append({"kind": "question", "data": model.model_dump(mode="json")})
                reports.append({"kind": "validation", "data": report.model_dump(mode="json")})
            if skill == "listening":
                audio_path = ROOT / "data" / "audio" / f"{passage_id}.mp3"
                audio_path.parent.mkdir(parents=True, exist_ok=True)
                wav_path = audio_path.with_suffix(".wav")
                subprocess.run(["espeak", "-v", "ru", "-s", "145", "-w", str(wav_path), spec["text"]], check=True)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-codec:a", "libmp3lame", "-q:a", "4", str(audio_path)], check=True)
                wav_path.unlink(missing_ok=True)
                duration = audio_duration_seconds(audio_path)
                p.audio_duration_seconds = duration
                asset = AudioAsset(
                    id=audio_id, path=f"data/audio/{passage_id}.mp3", content_hash=content_hash(spec["text"]),
                    transcript_hash=content_hash(spec["text"]), voice="eSpeak Russian male", rate="145 wpm",
                    engine="eSpeak", engine_version="system", duration_seconds=duration, validated=True,
                    license="Project-authored synthetic content; generated audio",
                )
                records.append({"kind": "audio", "data": asset.model_dump(mode="json")})
                # Replace passage record with duration populated.
                records[-(len(question_models)+2)] = {"kind": "passage", "data": p.model_dump(mode="json")}
    return records + reports


if __name__ == "__main__":
    output = ROOT / "data" / "starter_items.jsonl"
    records = make_records()
    with output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records to {output}")

"""Fifth ALES batch: original dialogues for 80 previously uncovered senses."""

SPECS = [
('e5_festival', 1, 'Planning a neighborhood event', [
('A', 'Встреча организаторов должна состояться в среду. На ней будем выбирать площадку для праздника.'),
('B', 'Кто может участвовать в обсуждении?'),
('A', 'Все жители района. После встречи мы решили объявить дату праздника. До этого объявления в газете не будет.')], '''
состояться|to take place|состояться|take place|be postponed;be canceled;be broadcast|What is the organizers’ meeting expected to do on Wednesday?|Собрание должно состояться завтра.
выбирать/выбрать|to choose, to elect|выбирать|choose|decorate;inspect;rent|What will the organizers do concerning the venue?|Завтра будем выбирать подарок для коллеги.
участвовать|to participate|участвовать|participate|vote by proxy;take minutes;lead the meeting|What activity does the second speaker ask about?|Я хочу участвовать в этом проекте.
объявлять/объявить|to announce|объявить|announce|change;confirm privately;cancel|What do the organizers intend to do with the festival date after meeting?|Решение обещали объявить утром.
'''),
('e5_arrival', 1, 'Arranging a guest visit', [
('A', 'Гости должны прибыть к вечеру. После станции они будут направляться в наш центр, поэтому я оставлю там ключи.'),
('B', 'Они собираются остаться на выходные?'),
('A', 'Да. Им разрешили пользоваться комнатой на втором этаже. Завтра уточню, сколько комплектов белья нужно приготовить.')], '''
прибывать/прибыть|to arrive|прибыть|arrive|depart;register;call|What are the guests expected to do by evening?|Посылка должна прибыть в пятницу.
направляться/направиться|to head for, to make for|направляться|head toward|call from;wait outside;avoid|What will the guests do in relation to the center after the station?|После обеда мы будем направляться к озеру.
оставаться/остаться|to remain, to stay, to be left|остаться|stay|return;work;perform|What weekend plan does the second speaker ask about?|Я решил остаться ещё на день.
пользоваться/воспользоваться|to use|пользоваться|use|renovate;sublet;photograph|What have the guests been allowed to do with the upstairs room?|Здесь можно пользоваться словарём.
'''),
('e5_workshop', 1, 'Checking progress in a workshop', [
('A', 'К работе над макетом можно приступить завтра. Мы хотим достичь нужной точности до конца месяца.'),
('B', 'А что будем делать со старым проектом?'),
('A', 'Его решили продолжить. Не всё удаётся сразу, поэтому оставим время на проверку обеих работ. В пятницу покажем первые результаты.')], '''
приступать/приступить|to begin|приступить|begin|return;make corrections;put an end|What can the team do with work on the model tomorrow?|К обсуждению можно приступить после перерыва.
достигать/достичь|to achieve|достичь|achieve|measure;reduce;reconsider|What does the team want to do concerning the required precision?|Мы надеемся достичь соглашения.
продолжать/продолжить|to continue|продолжить|continue|archive;divide;cancel|What was decided about the old project?|Разговор решили продолжить вечером.
удаваться/удаться|to succeed in, to manage|удаётся|succeeds|fails;becomes cheaper;gets approved|What does the speaker say does not always happen immediately?|Не всегда удаётся найти нужную книгу.
'''),
('e5_exhibition', 2, 'Discussing an exhibition design', [
('A', 'Основной зал уже подготовили. У нового стенда необычный вид, но директор пока его не оценил.'),
('B', 'Ты видел яркий плакат у входа?'),
('A', 'Да. Он относится к разделу про современность. Подпись ещё проверяют, а весь проект будут обсуждать на следующей неделе.')], '''
основной|basic, principal|Основной|main|temporary;smallest;outdoor|Which hall has been prepared?|Основной вход находится со стороны площади.
вид|look, appearance, kind, sort|вид|appearance|location;price;purpose|What is unusual about the new display stand?|После ремонта у дома совсем другой вид.
яркий|bright|яркий|bright|faded;handwritten;torn|How does the second speaker describe the entrance poster?|Для обложки выбрали яркий цвет.
современность|modernity, the present|современность|the present day|ancient history;the distant future;the Middle Ages|What period is the section associated with the poster about?|Автор часто пишет про современность.
'''),
('e5_forecast', 3, 'Weighing a preliminary forecast', [
('A', 'В докладе назван вероятный срок открытия центра. Пока мы можем только предполагать, каким будет расписание.'),
('B', 'Как ты оцениваешь сам проект?'),
('A', 'Он весьма интересный. Но число посетителей может значительно измениться после открытия соседнего музея. Поэтому окончательный план ещё не готов.')], '''
вероятный|probable|вероятный|probable|earliest permitted;previously announced;legally binding|How certain is the opening timeframe described in the report?|Это вероятный итог переговоров.
предполагать/предположить|to suppose|предполагать|make assumptions|make promises;give approval;raise objections|What can they currently do about the future schedule?|Пока можно лишь предполагать причину задержки.
весьма|highly, extremely|весьма|very|barely;occasionally;unexpectedly|To what degree does the speaker find the project interesting?|Этот вопрос весьма важен для команды.
значительно|considerably|значительно|considerably|slightly;temporarily;predictably|How much might visitor numbers change?|Цена может значительно вырасти к лету.
'''),
('e5_settings', 2, 'Checking instrument settings', [
('A', 'В инструкции указана допустимая величина нагрузки. Её нужно проверить перед началом работы.'),
('B', 'А уровень воды уже измерили?'),
('A', 'Да, результаты в журнале. Теперь нужно установить время следующей проверки. Я предложу утро, но сначала поговорю с начальником смены.')], '''
допустимый (допускать 40)|permissible|допустимая|permissible|average;recommended minimum;previously measured|How is the load value in the instructions characterized?|Это допустимая ошибка при таком измерении.
величина|value, quantity, size|величина|magnitude|duration;source;direction|Which aspect of the load is specified?|Эта величина зависит от температуры.
уровень|level|уровень|level|purity;temperature;flow rate|Which property of the water does the second speaker ask about?|Нужно проверить уровень масла.
устанавливать/установить|to establish, to set|установить|set|postpone;record;calculate retrospectively|What needs to be done about the next inspection time?|Комиссия должна установить срок подачи заявок.
'''),
('e5_maintenance', 2, 'Reviewing a maintenance plan', [
('A', 'В плане есть изменение: на поддержание здания выделят другую сумму. Точную цифру пришлют завтра.'),
('B', 'Получится поддерживать нужную температуру зимой?'),
('A', 'Инженер обещает проверить. Он также предлагает увеличить число датчиков, но закупку ещё не согласовали.')], '''
изменение|change|изменение|change|error;exception;objection|What does the first speaker identify in the plan?|В расписании есть одно изменение.
поддержание|maintenance|поддержание|upkeep|demolition;purchase;expansion|What purpose will the building allocation serve?|На поддержание порядка уходит много времени.
поддерживать/поддержать|to support, to maintain|поддерживать|maintain|lower;measure;predict|What do they hope to do with the required winter temperature?|Эта система помогает поддерживать связь.
увеличивать/увеличить|to increase|увеличить|increase|reduce;check;limit|What change in sensor numbers does the engineer propose?|Музей решил увеличить число экскурсий.
'''),
('e5_route', 1, 'Explaining a walking route', [
('A', 'Утром будем двигаться к реке. После моста надо следовать указателям, а не старой карте.'),
('B', 'Когда нужно покинуть лагерь?'),
('A', 'До восьми. Вчера группе пришлось продвигаться медленно. Сегодня мы тоже оставим запас времени и возьмём еду на весь день.')], '''
двигаться|to move|двигаться|move|look;call;return supplies|What will the group do toward the river in the morning?|По этой улице лучше двигаться пешком.
следовать/последовать|to follow, to go after, to be bound for|следовать|follow|replace;ignore;photograph|What should the group do with the signs after the bridge?|При работе нужно следовать инструкции.
покидать/покинуть|to leave, to desert, to abandon|покинуть|leave|set up;inspect;reach|What action concerning camp needs a time decision?|Посетителей попросили покинуть зал.
продвигаться/продвинуться|to move forward, to advance|продвигаться|advance|rest;pack;make calls|What did yesterday’s group have to do slowly?|Работа начала продвигаться быстрее.
'''),
('e5_incident', 3, 'Reviewing a workplace incident', [
('A', 'В журнале описано происшествие у склада. Мы пока не знаем, что именно произошло.'),
('B', 'Запись с камеры уже посмотрели?'),
('A', 'Да. На ней видно действие работника перед остановкой машины. Мастер проверит, могло ли оно вызвать сбой. До проверки выводов не будет.')], '''
происшествие|incident|происшествие|incident|inspection;celebration;delivery|What kind of event is described in the log?|Происшествие обсуждали на утреннем собрании.
происходить/произойти|to happen, to occur, to take place|произошло|happened|was approved;was repaired;was scheduled|What do they not yet know precisely?|Никто не понял, что произошло в коридоре.
действие|action|действие|action|identity;injury;opinion|What about the worker is visible on the recording?|Его действие удивило всех в комнате.
вызывать/вызвать|to cause|вызвать|cause|prevent;conceal;detect|What possible relationship between the action and the malfunction will be checked?|Такая ошибка может вызвать задержку.
'''),
('e5_interview', 2, 'Preparing a collector interview', [
('A', 'Обладатель коллекции согласился на интервью. Редактор просит обратить особое внимание на историю первого экспоната.'),
('B', 'У кого узнать подробности о времени встречи?'),
('A', 'Нужно обратиться к его помощнице. Сам коллекционер, говорят, обладает хорошей памятью, но заранее обещать ответы на все вопросы не стал.')], '''
обладатель|possessor|Обладатель|owner|critic;restorer;buyer|Who agreed to the interview?|Обладатель приза выступит после перерыва.
особый|special|особое|special|limited;equal;occasional|What kind of attention should the first exhibit’s history receive?|Для поездки нужно особое разрешение.
обращаться/обратиться|to turn, to appeal to|обратиться|turn to|replace;avoid;supervise|What should the interviewer do regarding the assistant?|За советом можно обратиться к преподавателю.
обладать|to possess|обладает|possesses|is losing;questions;exaggerates|How is the collector related to the good memory mentioned?|Этот материал обладает высокой прочностью.
'''),
('e5_anniversary', 1, 'Preparing an anniversary program', [
('A', 'Завтра музею исполнится двадцать лет. Утром будет торжественная церемония, а потом откроют выставку.'),
('B', 'Сколько времени займёт программа?'),
('A', 'Она будет длиться по крайней мере два часа. Билеты уже готовы, но окончательный список гостей нам ещё не прислали.')], '''
исполняться/исполниться|to be, to occur|исполнится|turns that many years old|closes for that many years;receives that many exhibits;extends its lease that many years|What does the mention of twenty years say about the museum tomorrow?|В мае моей сестре исполнится десять лет.
торжественная церемония|solemn ceremony|торжественная церемония|formal ceremony|private rehearsal;guided tour;staff briefing|What is scheduled in the morning?|После встречи начнётся торжественная церемония.
длиться/продлиться (длинный 21)|to last|длиться|last|start late;be repeated;be prepared|What is the program said to do for the stated period?|Перерыв будет длиться полчаса.
по крайней мере|at least|по крайней мере|at least|at most;exactly;less than|How should the stated two-hour duration be understood?|Нам нужно по крайней мере три стула.
'''),
('e5_training', 2, 'Organizing a training visit', [
('A', 'В район решили направить новую группу. До поездки нужно оснастить её всем необходимым.'),
('B', 'Кто будет проводить занятия?'),
('A', 'Антон. Он способный преподаватель и хочет развивать эту программу. Но сначала ему нужно обсудить расписание с местной школой.')], '''
направлять/направить|to direct, to send|направить|send|recall;recruit;dismiss|What did they decide to do with the new group?|Письмо нужно направить директору.
оснащать/оснастить|to equip|оснастить|equip|insure;register;divide|What must be done for the group before the trip?|Кабинет планируют оснастить компьютерами.
способный|capable|способный|capable|strict;inexperienced;retired|How is Anton described as a teacher?|Наш новый сотрудник очень способный.
развивать/развить|to develop|развивать|develop|replace;close;advertise|What does Anton want to do with the program?|Клуб помогает развивать интерес к чтению.
'''),
('e5_survey', 3, 'Organizing a regional survey', [
('A', 'Опрос решили провести в пятницу. Предварительный расчёт расходов уже готов, но его ещё должен проверить бухгалтер.'),
('B', 'А кто подготовит материалы для участников?'),
('A', 'Наша мастерская будет производить карточки. Молодые специалисты составляют половину команды, поэтому работу обсудят на общем собрании.')], '''
проводить/провести|to conduct, to hold, to carry out|провести|conduct|publish;postpone;analyze|What do they plan to do with the survey on Friday?|Встречу решили провести в библиотеке.
расчёт (рассчитывать 56)|estimate|расчёт|estimate|reimbursement;receipt;audit|What preliminary financial document is ready?|Для ремонта нужен новый расчёт.
производить/произвести|to produce, to make, to perform|производить|produce|distribute;translate;collect|What will the workshop do with the cards?|Фабрика будет производить мебель.
составлять/составить|to make up|составляют|make up|supervise;replace;train|What is the relationship of young specialists to half the team?|Эти книги составляют часть коллекции.
'''),
('e5_observatory', 3, 'Checking an observatory update', [
('A', 'Ночью был кратковременный перерыв в работе станции. Для проверки потребовалось дополнительное время.'),
('B', 'Причина уже известна?'),
('A', 'До сих пор нет. Старый прибор является частью общей системы, поэтому инженер проверит и соседние устройства. Отчёт обещают прислать вечером.')], '''
кратковременный|brief, of short duration|кратковременный|brief|unexpected;scheduled;repeated|How long was the interruption characterized as lasting?|Возможен кратковременный дождь.
потребовалось|was required|потребовалось|was required|was wasted;was promised;was saved|How was the extra time related to the inspection?|Для ответа потребовалось несколько минут.
до сих пор|until now|До сих пор|still, up to now|only at first;since yesterday;never again|What does the reply indicate about when the cause remained unknown?|До сих пор я не получил письма.
являться|to be|является|is|used to be;will replace;is separate from|How is the old instrument related to the overall system?|Этот документ является частью договора.
'''),
('e5_catalog', 3, 'Editing a collection catalog', [
('A', 'Редактор просит включить материал, связанный с архитектурой. Для меня это новая область, поэтому я проверю термины.'),
('B', 'Какое у директора отношение к этой части каталога?'),
('A', 'Пока не знаю. Он считает её полезной, но полное заключение обещал прислать только после обсуждения с коллегами.')], '''
связанный|connected with|связанный|connected with|opposed to;independent of;copied from|How should the requested material relate to architecture?|Это вопрос, связанный с поездкой.
область (f.)|oblast; field, area|область|field|administrative province;physical room;publication date|What does the first speaker mean by calling this something new to them?|Для него музыка — новая область.
отношение|relation|отношение|attitude|authority;appointment;contribution|What does the second speaker ask about the director?|Его отношение к работе изменилось.
считать|to consider; to count|считает|considers|counts;quotes;calculates|What is the director doing when describing this section as useful?|Она считает этот план удачным.
'''),
('e5_camp', 1, 'Recalling a summer camp', [
('A', 'На фотографии наш пионерский лагерь. Я помню, как мы учились прыгать на спортивной площадке.'),
('B', 'Что ты чувствуешь, когда смотришь на этот снимок?'),
('A', 'Радость. Я думал, что успел потерять альбом во время переезда, но вчера нашёл его в коробке. Другие снимки ещё не посмотрел.')], '''
пионерский лагерь|pioneer (youth) camp|пионерский лагерь|Pioneer youth camp|military academy;university campus;mountaineering base|What place is shown in the photograph?|Летом здесь работал пионерский лагерь.
прыгать/прыгнуть|to jump|прыгать|jump|throw;wrestle;balance|What did the children learn to do on the sports ground?|На занятии дети будут прыгать.
чувствовать/почувствовать|to feel|чувствуешь|feel|notice;remember;expect|What does the second speaker ask about while viewing the picture?|Ты чувствуешь усталость после дороги?
терять/потерять|to lose|потерять|lose|give away;damage;sell|What did the speaker think had happened to the album during the move?|Я боялся потерять ключ от комнаты.
'''),
('e5_road', 2, 'Discussing a road-safety exercise', [
('A', 'На схеме отмечена полоса встречного движения. У этого перекрёстка нельзя разворачиваться.'),
('B', 'Что случилось с машиной на учебной записи?'),
('A', 'Она столкнулась с ограждением. Камера успела упасть ещё до приезда полиции, поэтому конец записи ничего не показывает.')], '''
полоса встречного движения|oncoming traffic lane|полоса встречного движения|oncoming lane|bus lane;turning lane;emergency lane|What lane is marked on the diagram?|На плане выделена полоса встречного движения.
разворачиваться/развернуться|to turn around|разворачиваться|make a U-turn|park;accelerate;change lanes|What maneuver is prohibited at this intersection?|У ворот нельзя разворачиваться.
сталкиваться/столкнуться|to collide with|столкнулась|collided with|stopped beside;moved away from;drove around|What did the car do in relation to the barrier?|Лодка столкнулась с причалом.
падать/упасть|to fall|упасть|fall|stop recording;lose focus;overheat|What happened to the camera before police arrived?|Книга могла упасть за стол.
'''),
('e5_search', 2, 'Coordinating a search exercise', [
('A', 'Поиски начнутся утром. Главная примета участника — красная куртка, но фотографию нам пока не дали.'),
('B', 'Где он будет скрываться по условиям игры?'),
('A', 'В старом парке. У ворот организатор оставит след на песке. Других подсказок до начала не будет.')], '''
поиски|search|Поиски|search|negotiations;repairs;celebrations|What activity will begin in the morning?|Поиски документов заняли весь день.
примета|sign|примета|identifying feature|official role;favorite object;assigned destination|What function does the red jacket serve in describing the participant?|Его главная примета — необычная шляпа.
скрываться/скрыться|to hide (oneself), to disappear|скрываться|hide|train;perform;wait in line|What is the participant meant to do in the park?|В этой игре можно скрываться за деревьями.
след|trace; footprint|след|footprint|message;flag;map|What will the organizer leave in the sand?|На снегу остался след собаки.
'''),
('e5_archive', 2, 'Preparing a historical display', [
('A', 'В архиве нашли письмо, которое подписала королева. Рядом с ним покажут дневник про паломничество.'),
('B', 'О чём будет последний раздел?'),
('A', 'Про мир после долгих переговоров. Там же расскажут, как генерал после отставки поселился в небольшом городе. Тексты ещё проверяют по документам.')], '''
королева|queen|королева|queen|princess;duchess;countess|Who signed the letter found in the archive?|На портрете изображена королева.
паломничество|pilgrimage|паломничество|pilgrimage|diplomatic mission;trading voyage;military campaign|What journey is described in the diary?|Он написал книгу про паломничество.
мир|world, peace|мир|peace|the world;an alliance;a dispute|What does the final section discuss as following the long negotiations?|Они надеялись сохранить мир.
отставка|retirement|отставки|retirement|promotion;transfer;training|What event in the general’s career preceded his move?|После отставки офицер занялся живописью.
'''),
('e5_publication', 3, 'Discussing a historical publication', [
('A', 'В новой книге описаны деловые круги страны. Отдельная глава посвящена тому, как народ обсуждал независимость.'),
('B', 'Автор использует письма того времени?'),
('A', 'Да. В одном из них говорится, что свобода важнее спокойной жизни. На встрече читатели смогут обсудить эту мысль, но дату ещё не назначили.')], '''
деловые круги|business circles|деловые круги|business circles|academic circles;military leadership;religious communities|What group is described in the new book?|Местные деловые круги поддержали выставку.
народ|people|народ|the people|the cabinet;the army;the court|Who discussed the issue in the separate chapter?|Народ ждал новостей с площади.
независимость|independence|независимость|independence|prosperity;security;unity|What issue did that chapter’s discussion concern?|В статье обсуждается независимость страны.
свобода|freedom, liberty|свобода|freedom|wealth;fame;stability|What does the letter place above a quiet life?|Для героя книги важна свобода.
'''),
]

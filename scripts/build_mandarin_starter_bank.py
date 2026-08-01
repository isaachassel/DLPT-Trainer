from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.constants import ILR_THETA, LETTERS
from core.models import AudioAsset, GenerationMetadata, PassageItem, QuestionItem, ValidationReport
from core.validation import content_hash, target_unit_count, validate_passage, validate_question


def q(stem, correct, wrong, evidence, qtype):
    return (stem, correct, wrong, evidence, qtype)


READING = [
    dict(level="0", genre="sign", topic="Public information", subtopic="library hours",
         orientation="A sign at a library entrance.", text="图书馆今天下午三点关门。",
         questions=[
             q("What place does the sign concern?", "A library", ["A hospital", "A station", "A restaurant"], "图书馆", "prominent detail"),
             q("When will it close today?", "At 3:00 p.m.", ["At noon", "At 5:00 p.m.", "At 8:00 p.m."], "下午三点关门", "prominent detail"),
             q("What is the sign doing?", "Giving today's closing time", ["Advertising a new book", "Requesting volunteers", "Changing an address"], "今天下午三点关门", "main idea"),
         ]),
    dict(level="0+", genre="message", topic="Daily life", subtopic="package pickup",
         orientation="A short mobile-phone message.", text="你的快递到了，请下班后到一楼前台领取。",
         questions=[
             q("What has arrived?", "A package", ["A coworker", "A meal", "A taxi"], "快递到了", "prominent detail"),
             q("Where should it be picked up?", "At the first-floor front desk", ["At the train station", "At a nearby store", "At the sender's home"], "一楼前台领取", "prominent detail"),
             q("When should the recipient go?", "After work", ["Before breakfast", "At lunchtime", "Next weekend"], "下班后", "sequence"),
         ]),
    dict(level="1", genre="notice", topic="Transportation", subtopic="bus detour",
         orientation="A notice posted at a bus stop.", text="因为前面的道路正在施工，十五路公交车今天不经过人民广场。去市中心的乘客请在下一站换乘地铁二号线。",
         questions=[
             q("Why is the bus route changed?", "Because the road is under construction", ["Because the driver is ill", "Because of heavy snow", "Because the bus is full"], "道路正在施工", "cause and effect"),
             q("Which location will the bus skip?", "People's Square", ["The airport", "The university", "The hospital"], "不经过人民广场", "prominent detail"),
             q("What should passengers going downtown do?", "Transfer to Metro Line 2", ["Wait for Bus 15 tomorrow", "Walk to People's Square", "Take a taxi from this stop"], "换乘地铁二号线", "sequence"),
         ]),
    dict(level="1", genre="email", topic="Workplace", subtopic="meeting materials",
         orientation="An email from a team leader.", text="各位同事，明天上午的会议改到十点开始。请大家九点半以前把上个月的销售数据发给我，我会把这些数据放进会议材料。",
         questions=[
             q("What changed about the meeting?", "Its starting time", ["Its topic", "Its location", "Its participants"], "改到十点开始", "prominent detail"),
             q("What must employees send?", "Last month's sales data", ["Their vacation requests", "A customer list", "Next year's budget"], "上个月的销售数据", "prominent detail"),
             q("Why does the leader need the data?", "To include it in the meeting materials", ["To publish it on a website", "To send it to customers", "To calculate employee leave"], "放进会议材料", "cause and effect"),
         ]),
    dict(level="1+", genre="announcement", topic="Education", subtopic="weekend course",
         orientation="An announcement from a community center.", text="社区中心下个月开设周末电脑课，主要帮助老年人学习网上挂号和手机付款。课程免费，但教室只能坐二十人。报名人数如果超过二十人，中心会在星期日下午增加一班。",
         questions=[
             q("Who is the course mainly intended to help?", "Older adults", ["Primary-school teachers", "Foreign tourists", "New employees"], "帮助老年人", "prominent detail"),
             q("What will students learn?", "Online registration and mobile payment", ["Computer repair and coding", "Photography and video editing", "English and calligraphy"], "网上挂号和手机付款", "prominent detail"),
             q("What happens if more than twenty people register?", "An extra Sunday afternoon class will be added", ["The fee will increase", "Registration will be canceled", "The class will move online"], "星期日下午增加一班", "cause and effect"),
         ]),
    dict(level="1+", genre="news brief", topic="Public health", subtopic="mobile clinic",
         orientation="A local news brief about medical services.", text="从本周起，一辆流动医疗车每周三到城北的三个村子服务。居民可以免费量血压，也可以向医生咨询常见的慢性病。需要做进一步检查的人会拿到市医院的预约单。",
         questions=[
             q("How often will the mobile clinic visit?", "Every Wednesday", ["Every morning", "Twice a month", "Only on holidays"], "每周三", "prominent detail"),
             q("Which service is free?", "Blood-pressure measurement", ["All prescription medicine", "Hospital surgery", "Dental treatment"], "免费量血压", "prominent detail"),
             q("What will people needing more tests receive?", "A city-hospital appointment slip", ["A cash payment", "A home medical device", "A train ticket"], "市医院的预约单", "sequence"),
         ]),
    dict(level="2", genre="report", topic="Environment", subtopic="food-waste pilot",
         orientation="A municipal report on a recycling pilot.", text="市政府去年在十个居民区试行厨余垃圾单独回收。开始时，不少居民分不清哪些垃圾可以投入绿色垃圾桶，导致处理成本上升。后来，社区工作人员通过短视频和现场演示说明分类方法，错误投放的比例明显下降。市政府决定今年把项目扩大到全市，但会先培训物业人员，因为他们最常回答居民的问题。",
         questions=[
             q("What problem occurred early in the pilot?", "Residents often sorted waste incorrectly", ["Green bins were stolen", "Collection trucks arrived late", "Food waste was not produced"], "分不清哪些垃圾", "prominent detail"),
             q("What helped reduce the error rate?", "Videos and in-person demonstrations", ["Higher disposal fees", "Fewer collection days", "A ban on green bins"], "短视频和现场演示", "cause and effect"),
             q("Why will property staff be trained first?", "They frequently answer residents' questions", ["They manufacture the bins", "They approve the city budget", "They drive every collection truck"], "最常回答居民的问题", "cause and effect"),
         ]),
    dict(level="2", genre="news report", topic="Economics", subtopic="night market policy",
         orientation="A news report about a city night market.", text="为了吸引游客，海州市去年允许老城区商店在夏季延长营业时间。游客数量确实增加了，但附近居民对噪音和停车问题提出了很多意见。今年，市里没有取消夜间营业，而是要求商家在晚上十点后停止户外音乐，并为居民保留部分停车位。有关部门表示，新规定的目的不是限制商业活动，而是在旅游收入和社区生活之间寻找平衡。",
         questions=[
             q("What was one result of the extended hours?", "More tourists visited", ["All residents moved away", "Parking became free", "Shops closed earlier"], "游客数量确实增加", "prominent detail"),
             q("What must businesses stop after 10 p.m.?", "Outdoor music", ["Food sales", "Indoor lighting", "Online orders"], "停止户外音乐", "prominent detail"),
             q("What balance is the city seeking?", "Tourism income and community life", ["Public schools and hospitals", "Exports and imports", "Bus service and rail service"], "旅游收入和社区生活之间", "main idea"),
         ]),
    dict(level="2+", genre="commentary", topic="Technology", subtopic="digital public services",
         orientation="A newspaper commentary on digital government services.", text="把公共服务搬到网上，通常被视为提高效率的办法。对熟悉智能手机的人来说，在线申请确实减少了排队时间。然而，效率不能只用系统处理了多少申请来衡量。如果老年人、残障人士或网络条件较差的居民无法顺利使用平台，政府只是把服务窗口的队伍变成了看不见的数字障碍。因此，保留必要的线下渠道并不是拒绝技术，而是承认公共服务的价值还包括可及性。真正成熟的数字化，应当让不同能力的人都能完成同一件事。",
         questions=[
             q("What limitation does the writer see in measuring efficiency?", "It may ignore people who cannot use the platform", ["It counts too many office buildings", "It focuses only on employee salaries", "It prevents any online application"], "无法顺利使用平台", "inference"),
             q("How does the writer view keeping offline service?", "As necessary for accessibility", ["As proof that technology has failed", "As a temporary tourism program", "As a way to reduce public services"], "还包括可及性", "speaker/writer intent"),
             q("What defines mature digitalization in the passage?", "People with different abilities can complete the same task", ["Every service eliminates staff", "All residents buy new phones", "Applications are processed overseas"], "不同能力的人都能完成同一件事", "main idea"),
         ]),
    dict(level="2+", genre="analysis", topic="Culture and society", subtopic="museum access",
         orientation="An analysis of efforts to broaden museum attendance.", text="一些博物馆把参观人数增长当作开放程度提高的证据，但总人数并不能说明谁真正获得了文化资源。免费日可能带来大量游客，却未必能吸引平时因交通、时间或语言障碍而不来的人。某市博物馆调查后发现，周末延长开放时间对上班族最有效，多语种讲解则明显增加了新移民家庭的停留时间。这说明，降低票价只是第一步。博物馆如果希望服务更广泛的公众，就必须先理解不同群体不来的具体原因，再设计有针对性的措施。",
         questions=[
             q("Why can total attendance be misleading?", "It does not show which groups gained access", ["It excludes all weekend visitors", "It counts only foreign tourists", "It measures ticket prices incorrectly"], "不能说明谁真正获得", "inference"),
             q("Which measure especially helped working people?", "Longer weekend hours", ["Free weekday parking", "Shorter exhibits", "Online ticket auctions"], "周末延长开放时间", "prominent detail"),
             q("What approach does the analysis recommend?", "Identify each group's specific barrier before acting", ["Use the same discount for everyone", "Replace exhibits every week", "Measure success only by revenue"], "理解不同群体不来的具体原因", "main idea"),
         ]),
    dict(level="3", genre="policy analysis", topic="International relations", subtopic="regional agreements",
         orientation="An analytical excerpt about regional cooperation.", text="区域合作常以签署协议的数量来展示成果，但文件增加并不必然意味着合作更牢固。各方在利益一致时容易发表共同声明，真正的考验出现在经济放缓、国内政治变化或安全危机迫使成员承担成本的时候。此时，如果合作机制只能依靠领导人之间的私人关系，它往往会随着人事变化而失去作用。相反，能够公开处理分歧、允许成员调整部分承诺、同时维护核心规则的制度，看似不够整齐，却可能更有韧性。由此看来，联盟的稳定不应以没有争议来判断，而应看争议是否能够在不破坏长期合作的情况下得到管理。",
         questions=[
             q("What does the author consider the real test of cooperation?", "Whether it survives periods when members must bear costs", ["Whether it produces many ceremonial statements", "Whether all leaders are personal friends", "Whether it avoids every domestic election"], "迫使成员承担成本的时候", "main idea"),
             q("Why are leader-to-leader relationships insufficient?", "Personnel changes can weaken the mechanism", ["They make agreements too public", "They eliminate economic interests", "They prevent any security discussion"], "随着人事变化而失去作用", "cause and effect"),
             q("How should alliance stability be judged?", "By whether disputes are managed without destroying long-term cooperation", ["By whether disputes never occur", "By the number of signed documents", "By how quickly members change leaders"], "不破坏长期合作", "relationship of ideas"),
         ]),
    dict(level="3", genre="editorial", topic="Environment", subtopic="urban climate adaptation",
         orientation="An editorial on how cities evaluate climate-adaptation projects.", text="面对极端高温，许多城市喜欢公布新种了多少棵树、增加了多少平方米绿地，因为这些数字直观，也容易写进年度报告。然而，项目的真正效果取决于树种能否存活、树荫是否覆盖最需要降温的街区，以及租房者和低收入居民是否会因环境改善而被上涨的房租挤走。若只追求可见的建设数量，绿化甚至可能扩大原有的不平等。评估政策时，城市不仅要测量平均温度变化，还应长期追踪不同社区获得的健康收益和居住稳定性。气候适应不是一次性的景观工程，而是对公共资源如何分配的持续选择。",
         questions=[
             q("What is the editorial's main criticism of simple construction totals?", "They can hide unequal real-world outcomes", ["They are impossible to publish", "They always reduce tree survival", "They prevent temperature measurement"], "可能扩大原有的不平等", "main idea"),
             q("What unintended effect does the author mention?", "Improved areas may become unaffordable to current residents", ["Trees may stop all public transit", "Green areas may eliminate rental housing", "Reports may ban low-income residents"], "被上涨的房租挤走", "inference"),
             q("What additional outcomes should cities track?", "Health benefits and housing stability by community", ["Only average citywide temperature", "The number of annual reports", "Tourist purchases near parks"], "健康收益和居住稳定性", "prominent detail"),
         ]),
]


LISTENING = [
    dict(level="0", genre="announcement", topic="Transportation", subtopic="train platform", orientation="A station announcement.", text="开往上海的列车在三号站台上车。",
         questions=[q("Where should passengers board?", "Platform 3", ["Platform 1", "Platform 5", "The bus terminal"], "三号站台", "prominent detail"), q("Where is the train going?", "Shanghai", ["Beijing", "Nanjing", "Guangzhou"], "开往上海", "prominent detail"), q("What kind of message is this?", "A boarding announcement", ["A weather warning", "A restaurant order", "A school lesson"], "列车", "main idea")]),
    dict(level="0+", genre="voicemail", topic="Daily life", subtopic="dinner delay", orientation="A short voicemail from a family member.", text="我今天晚一点回家，你们先吃饭，不用等我。",
         questions=[q("What will the speaker do?", "Come home late", ["Leave home early", "Cook breakfast", "Call a taxi"], "晚一点回家", "prominent detail"), q("What should the family do?", "Eat without waiting", ["Meet at a restaurant", "Save all the food", "Wait outside"], "先吃饭", "sequence"), q("What is the purpose of the message?", "To explain a delay", ["To invite guests", "To cancel a trip", "To request money"], "不用等我", "main idea")]),
    dict(level="1", genre="service announcement", topic="Public information", subtopic="water outage", orientation="A neighborhood loudspeaker announcement.", text="因为水管维修，明天上午八点到十一点小区停水。请居民提前准备好生活用水。维修结束后，供水会自动恢复。",
         questions=[q("Why will the water be off?", "Pipe repairs", ["A power shortage", "Flooding", "Unpaid bills"], "水管维修", "cause and effect"), q("When will the outage begin?", "At 8 a.m.", ["At 6 a.m.", "At 11 a.m.", "At noon"], "上午八点", "prominent detail"), q("What should residents do?", "Store water in advance", ["Leave the neighborhood", "Call the police", "Pay a repair fee"], "提前准备好生活用水", "sequence")]),
    dict(level="1", genre="conversation", topic="Commerce", subtopic="product return", orientation="A customer speaks with a store employee.", text="顾客说这件衬衫太小，想换大一号。店员检查后说，大号今天没有货，可以星期五来取，也可以现在退款。顾客决定星期五再来。",
         questions=[q("What is wrong with the shirt?", "It is too small", ["It is damaged", "It is too expensive", "It is the wrong color"], "衬衫太小", "prominent detail"), q("When will the larger size be available?", "Friday", ["Today", "Monday", "Next month"], "星期五来取", "prominent detail"), q("What does the customer decide?", "Return on Friday", ["Take a refund now", "Buy a smaller shirt", "Order online today"], "决定星期五再来", "sequence")]),
    dict(level="1+", genre="radio report", topic="Accidents and disasters", subtopic="storm cleanup", orientation="A local radio report after a storm.", text="昨夜的大风吹倒了公园里的几棵树。工作人员今天上午关闭了北门，正在清理道路。南门仍然开放，但儿童游乐区要到明天下午才能使用。市民经过施工区域时应该听从工作人员的指示。",
         questions=[q("Why is the north gate closed?", "Workers are clearing fallen trees", ["A festival is taking place", "Tickets are sold out", "The gate is being painted"], "正在清理道路", "cause and effect"), q("Which entrance remains open?", "The south gate", ["The north gate", "The east gate", "No entrance"], "南门仍然开放", "prominent detail"), q("When can the play area be used?", "Tomorrow afternoon", ["This morning", "Tonight", "Next week"], "明天下午才能使用", "prominent detail")]),
    dict(level="1+", genre="interview", topic="Education", subtopic="school garden", orientation="A short interview with a teacher.", text="记者问学校为什么把一块空地改成菜园。老师说，学生在科学课上会观察植物生长，也会把收获的蔬菜送给附近的老人。原来只有高年级参加，现在低年级每个月也有一次活动。",
         questions=[q("Why was the garden created?", "For science learning and community giving", ["To sell vegetables for profit", "To replace the sports field", "To train professional farmers"], "观察植物生长", "main idea"), q("Who receives the vegetables?", "Older people nearby", ["Restaurant customers", "School athletes", "City officials"], "送给附近的老人", "prominent detail"), q("What recently changed?", "Younger students now participate monthly", ["The garden moved indoors", "Science classes were canceled", "Only teachers may enter"], "低年级每个月也有一次活动", "relationship of ideas")]),
    dict(level="2", genre="news report", topic="Economics", subtopic="rural delivery", orientation="A consumer-news report.", text="一家超市在偏远乡镇试行食品配送三个月。顾客可以用手机应用下单，也可以打电话。公司原来认为年轻人会使用应用，老年人会打电话，但实际情况更复杂：不少网络不稳定地区的顾客，不分年龄，都选择电话。公司因此决定扩大服务时增加电话接线员，同时改善应用在低速网络下的功能。",
         questions=[q("What assumption proved too simple?", "That channel choice would mainly depend on age", ["That nobody wanted delivery", "That phone orders cost less", "That young people lived in cities"], "实际情况更复杂", "inference"), q("Who often chose phone ordering?", "Customers in areas with unstable internet", ["Only company employees", "Only elderly city residents", "People with no food order"], "网络不稳定地区的顾客", "prominent detail"), q("How will the company respond?", "Add phone staff and improve the app for slow networks", ["End phone ordering", "Serve only young customers", "Close the pilot immediately"], "增加电话接线员", "cause and effect")]),
    dict(level="2", genre="briefing", topic="Environment", subtopic="river monitoring", orientation="A public briefing on river quality.", text="环保部门介绍说，河水的平均污染指数比去年下降了，但两个支流在暴雨后仍会出现短时间污染。调查发现，雨水把道路上的油污带进了河里。市里计划在重点路段增加过滤设施，并在下一次雨季公布每周监测结果。负责人强调，年度平均数字改善，不代表所有时间和地点都安全。",
         questions=[q("What causes the short pollution spikes?", "Rain washes road oil into the river", ["Factories release hot water daily", "Fish block the tributaries", "Monitoring equipment adds chemicals"], "油污带进了河里", "cause and effect"), q("What will the city add?", "Filtering equipment", ["New fishing docks", "Tourist boats", "Drinking fountains"], "增加过滤设施", "prominent detail"), q("Why does the official qualify the annual average?", "Conditions still vary by time and place", ["No measurements were taken", "The average is higher than last year", "All tributaries are always safe"], "不代表所有时间和地点都安全", "inference")]),
    dict(level="2+", genre="commentary", topic="Culture and society", subtopic="public libraries", orientation="A radio commentator discusses libraries.", text="电子书普及以后，有人认为公共图书馆会逐渐失去作用。这种判断把图书馆只看成存放纸质书的地方。事实上，学生在那里学习，老年人请工作人员帮助使用数字服务，社区组织也借用空间举办活动。纸质书借阅量下降，可能说明使用方式改变，而不一定说明公共价值降低。评价图书馆时，如果只计算借出了多少本书，就会忽略它作为学习空间、技术入口和社区平台的功能。",
         questions=[q("What assumption does the commentator challenge?", "That libraries matter only as places for printed books", ["That electronic books exist", "That students need quiet spaces", "That communities hold events"], "只看成存放纸质书的地方", "speaker/writer intent"), q("What may lower print circulation indicate?", "A change in how people use libraries", ["A complete loss of public value", "A ban on community events", "An increase in book prices"], "使用方式改变", "inference"), q("What is wrong with counting loans alone?", "It misses several other public functions", ["It counts digital books twice", "It measures building size", "It excludes all students"], "忽略它作为学习空间", "main idea")]),
    dict(level="2+", genre="panel discussion", topic="Technology", subtopic="remote work", orientation="An excerpt from a workplace panel discussion.", text="主持人问远程办公是否提高了效率。经理说，个人写报告时干扰少，速度确实更快，但新员工很难通过视频会议了解团队里没有写下来的工作习惯。另一位员工补充说，问题不在于选择办公室还是家，而在于不同任务需要不同环境。公司后来规定，每个项目开始和结束时必须面对面开会，中间阶段由团队自己决定。这样做不是折中，而是把协作方式和任务阶段联系起来。",
         questions=[q("What difficulty affects new employees?", "Learning unwritten team practices", ["Writing individual reports", "Finding a home computer", "Receiving a salary"], "没有写下来的工作习惯", "prominent detail"), q("What principle underlies the new policy?", "Work setting should match the project stage", ["Everyone should always work at home", "Only managers choose locations", "Video meetings should be banned"], "不同任务需要不同环境", "main idea"), q("When are in-person meetings required?", "At the beginning and end of each project", ["Every afternoon", "Only during hiring", "Throughout the middle stage"], "开始和结束时必须面对面开会", "sequence")]),
    dict(level="3", genre="analytical interview", topic="International relations", subtopic="supply-chain cooperation", orientation="An analytical interview on regional economic cooperation.", text="采访者问，为什么一些国家在危机后强调供应链自主，却又继续签署区域合作协议。学者回答说，这两种做法表面矛盾，实际上反映了同一个担忧：没有国家愿意把关键物资完全交给单一来源。所谓自主，并不一定意味着全部在国内生产，而是保留替代供应商、储备和共同应急机制。区域协议如果只追求最低成本，遇到危机就很脆弱；如果允许成员承担一定的日常成本来换取备用能力，合作反而更可靠。因此，判断协议是否成功，不能只看贸易额是否增长，还要看它是否在压力出现时提供了真正的选择。",
         questions=[q("How does the scholar reconcile autonomy and cooperation?", "Both can reduce dependence on a single source", ["Autonomy ends all regional trade", "Cooperation requires one supplier", "They address unrelated concerns"], "完全交给单一来源", "relationship of ideas"), q("What tradeoff can make cooperation more reliable?", "Accepting routine costs to preserve backup capacity", ["Eliminating all reserves", "Choosing only the cheapest supplier", "Reducing every trade flow"], "日常成本来换取备用能力", "inference"), q("How should an agreement's success be judged?", "By whether it provides options under pressure", ["Only by growth in trade volume", "By the number of public speeches", "By complete domestic production"], "压力出现时提供了真正的选择", "main idea")]),
    dict(level="3", genre="policy debate", topic="Public policy", subtopic="algorithmic decisions", orientation="An excerpt from a policy debate about automated decisions.", text="一位代表主张，政府使用算法分配社会服务，可以减少工作人员的主观偏见。另一位代表回应说，统一规则并不自动等于公平，因为历史数据本身可能反映过去的不平等，而且受到影响的人往往不知道如何质疑系统。双方最后同意，争论的重点不应是算法能不能犯错——任何制度都会犯错——而是谁能够发现错误、解释决定并承担责任。如果自动化提高了处理速度，却让决定过程无法审查，它只是把偏见从个人判断转移到了技术结构中。透明度也不只是公开一段代码，而是让普通人能够理解影响自己的理由，并有实际可用的申诉渠道。",
         questions=[q("What shared conclusion do the speakers reach?", "Accountability and error correction matter more than assuming perfection", ["Algorithms never make mistakes", "Human decisions contain no bias", "All code must be kept secret"], "谁能够发现错误", "relationship of ideas"), q("What risk can faster automation create?", "Bias may become harder to examine", ["Every application takes longer", "Historical data disappears", "No services are allocated"], "决定过程无法审查", "inference"), q("How does the passage define meaningful transparency?", "People can understand decisions and use an appeal process", ["Publishing code without explanation", "Removing all human responsibility", "Keeping decisions confidential"], "实际可用的申诉渠道", "main idea")]),
]


def duration_seconds(path: Path) -> float:
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip()
    return float(output)


def build_records(audio_dir: Path) -> list[dict]:
    records: list[dict] = []
    metadata = GenerationMetadata(provider="manual", model="human-authored", prompt_version="mandarin-starter-bank-v1")
    for skill, specs in (("reading", READING), ("listening", LISTENING)):
        for p_index, spec in enumerate(specs, start=1):
            prefix = "zh_r" if skill == "reading" else "zh_l"
            pid = f"{prefix}{p_index:03d}"
            qids = [f"{pid}_q{i}" for i in range(1, 4)]
            questions: list[QuestionItem] = []
            for q_index, raw in enumerate(spec["questions"]):
                stem, correct, wrong, evidence, qtype = raw
                correct_key = LETTERS[(p_index + q_index) % 4]
                values = iter(wrong)
                choices = {letter: (correct if letter == correct_key else next(values)) for letter in LETTERS}
                questions.append(QuestionItem(
                    id=qids[q_index], passage_id=pid, stem_en=stem, choices=choices,
                    correct_key=correct_key,
                    rationale_en="The cited source phrase directly supports this answer.",
                    evidence_ru=evidence, question_type=qtype, target_ilr=spec["level"],
                    provisional_difficulty=ILR_THETA[spec["level"]], generation=metadata,
                ))
            text = spec["text"]
            audio_asset = None
            audio_path = audio_dir / f"{pid}.mp3"
            duration = None
            audio_id = None
            voice_metadata = {}
            if skill == "listening":
                if not audio_path.exists() or audio_path.stat().st_size < 512:
                    raise FileNotFoundError(f"Missing Mandarin starter audio: {audio_path}")
                duration = duration_seconds(audio_path)
                audio_id = f"a_{pid}"
                voice_metadata = {"voice": "zh-CN-XiaoxiaoNeural", "synthetic": True}
                audio_asset = AudioAsset(
                    id=audio_id, path=f"data/audio/{audio_path.name}", content_hash=content_hash(text),
                    voice="zh-CN-XiaoxiaoNeural", rate="+0%", engine="edge-tts",
                    engine_version="7.2.8", duration_seconds=duration,
                    transcript_hash=content_hash(text), license="Project-authored synthetic content; generated audio",
                    synthetic_tts=True, validated=True,
                )
            passage = PassageItem(
                id=pid, language="zh-CN", skill=skill, target_ilr=spec["level"],
                provisional_difficulty=ILR_THETA[spec["level"]], genre=spec["genre"],
                topic=spec["topic"], subtopic=spec["subtopic"], orientation_en=spec["orientation"],
                passage_ru=text, word_count=target_unit_count(text, "zh-CN"),
                audio_duration_seconds=duration,
                segment_count=max(1, len([part for part in re.split(r"(?<=[。！？])", text) if part.strip()])),
                question_ids=qids, audio_asset_id=audio_id, voice_metadata=voice_metadata,
                generation=metadata, provenance={"author": "project starter-bank team", "method": "human-authored synthetic Mandarin practice content"},
                license="Project-authored synthetic content; MIT repository license",
                vocabulary_metadata={"provisional_ilr": spec["level"], "writing_system": "simplified Chinese"},
                discourse_metadata={"complexity_basis": "discourse and reasoning demand, not length alone"},
                content_hash=content_hash(text), duplicate_detection_hash=content_hash(text),
            )
            p_report = validate_passage(passage, questions)
            q_reports = [validate_question(question, passage) for question in questions]
            errors = p_report.failure_reasons + [reason for report in q_reports for reason in report.failure_reasons + report.ambiguity_flags]
            if errors:
                raise ValueError(f"{pid} failed validation: {sorted(set(errors))}")
            records.append({"kind": "passage", "data": passage.model_dump(mode="json")})
            records.extend({"kind": "question", "data": question.model_dump(mode="json")} for question in questions)
            if audio_asset:
                records.append({"kind": "audio", "data": audio_asset.model_dump(mode="json")})
            records.append({"kind": "validation", "data": ValidationReport(status="accepted", deterministic_checks=p_report.deterministic_checks).model_dump(mode="json")})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the validated Mandarin starter bank after audio has been generated.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "mandarin_starter_items.jsonl")
    parser.add_argument("--audio-dir", type=Path, default=ROOT / "data" / "audio")
    args = parser.parse_args()
    records = build_records(args.audio_dir)
    args.output.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    print(f"Wrote {len(records)} validated records to {args.output}")


if __name__ == "__main__":
    main()

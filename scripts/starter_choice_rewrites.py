"""Targeted starter-bank choice rewrites that remove material answer-length cues.

The mappings retain the original keyed proposition while making distractors
parallel in grammar, length, and specificity. Both bank builders import this
module, and the command-line entry point can upgrade an existing JSONL bank
without regenerating audio.
"""

from __future__ import annotations

import json
from pathlib import Path


CHOICE_REWRITES: dict[str, dict[str, str]] = {
    "r002_q2": {"A": "A person named Masha.", "B": "The writer's younger brother.", "C": "The writer's workplace manager.", "D": "The writer's school teacher."},
    "r006_q1": {"A": "All municipal service offices should close to reduce costs.", "B": "Older residents should obtain all municipal assistance from relatives.", "C": "Online municipal applications should be restricted to registered businesses.", "D": "Digital services should expand without eliminating in-person help."},
    "r006_q2": {"A": "Some residents still face difficulty using digital systems.", "B": "Some relatives refuse to help older residents with applications.", "C": "Online municipal systems always cost more than staffed offices.", "D": "Municipal employees oppose every change to public service delivery."},
    "r006_q4": {"A": "A program offered only during the local municipal election period.", "B": "A permanent prohibition on offering any government services online.", "C": "A temporary mixed system with online and in-person options.", "D": "A permanent transfer of public services to private companies."},
    "r007_q3": {"A": "Long-term economic growth versus short-term population decline.", "B": "Personal friendship between leaders versus wider cultural exchange.", "C": "Ceremonial agreement versus institutional performance under pressure.", "D": "Regional trade agreements versus growth in international tourism."},
    "r009_q3": {"A": "So the director can cancel the staff meeting scheduled for tomorrow.", "B": "So their data can be added to the shared presentation.", "C": "So employees can leave the office early tomorrow afternoon.", "D": "So August planning topics can be removed from the discussion."},
    "r009_q4": {"A": "Video conference equipment and upcoming business travel plans.", "B": "Employee training schedules and annual leave requests.", "C": "Quarterly results and the August work plan.", "D": "New hiring needs and planned office repair projects."},
    "r009_q5": {"A": "Join the scheduled video conference before submitting any report.", "B": "Prepare an entirely separate meeting about the August plan.", "C": "Rewrite the full agenda for tomorrow's staff meeting.", "D": "Submit their reports by the end of today."},
    "r010_q2": {"A": "How residents can safely open a new bank account.", "B": "How to identify callers pretending to be bank employees.", "C": "How retired officers can request a police pension.", "D": "How customers can repair a damaged mobile phone."},
    "r011_q1": {"A": "That museums should display more historical objects to visitors.", "B": "That most museum visitors prefer longer weekend opening hours.", "C": "That cultural institutions always require direct public funding.", "D": "That free admission alone makes a museum accessible."},
    "r011_q3": {"A": "A formal legal prohibition against charging any admission fee.", "B": "A nominal benefit that may not produce real access.", "C": "A membership benefit available only to museum employees.", "D": "A temporary admission discount offered during formal public events."},
    "r011_q4": {"A": "How many accessible entrances and doors the museum building has.", "B": "How much money the museum collection is officially worth.", "C": "Who can actually enter and gain a meaningful experience.", "D": "How frequently the museum changes its standard admission prices."},
    "r012_q1": {"A": "They rely too heavily on employee interviews rather than workplace observation.", "B": "They measure the costs of worker training instead of employment changes.", "C": "They assume new technology never changes required worker qualifications.", "D": "They focus on job counts and miss changes within occupations."},
    "r012_q2": {"A": "Stable job numbers can hide major changes in work content.", "B": "Companies eventually stop reporting complete employee totals to government labor statisticians.", "C": "Automated workplace systems create only temporary and unstable employment positions.", "D": "Workers routinely change their official job titles without changing duties."},
    "r012_q5": {"A": "Complete rejection of every form of modern workplace technology.", "B": "Unqualified enthusiasm for replacing most human workers with machines.", "C": "Complete indifference toward changes in employee skills and qualifications.", "D": "Analytical caution rather than simple support or opposition."},
    "l002_q3": {"A": "To explain a late arrival and adjust dinner plans.", "B": "To report that an important kitchen appliance has broken.", "C": "To ask the listener for detailed directions back home.", "D": "To invite the listener to share breakfast the next morning."},
    "l004_q2": {"A": "Visit a different medical clinic at the original appointment time.", "B": "Call the clinic by the end of the day.", "C": "Send the clinic a written letter sometime during the next week.", "D": "Arrive at the original appointment time without calling the clinic."},
    "l007_q1": {"A": "Tax incentives work best as one part of a broader development strategy.", "B": "Infrastructure matters only after every temporary regional tax incentive has fully expired.", "C": "Companies choose their business locations based entirely on the lowest available tax rates.", "D": "Regions should eliminate all financial incentives for attracting new investment."},
    "l007_q2": {"A": "Workers always move away from regions that offer lower business tax rates.", "B": "Regions may spend heavily without creating conditions that keep firms.", "C": "Local infrastructure automatically becomes less expensive when tax incentives increase.", "D": "Companies are legally required to reject every regional tax discount offered."},
    "l011_q2": {"A": "To reach interests underrepresented in the online response.", "B": "To recruit additional workers for the upcoming construction phase.", "C": "To announce the final project design to residents immediately.", "D": "To replace every public comment previously submitted through the website."},
    "l012_q2": {"A": "Political effects appear before any economic measures officially begin.", "B": "All trade sanctions end automatically within a single working week.", "C": "Some consequences may emerge only after a delay.", "D": "International trade always recovers immediately after new measures begin."},
    "l012_q3": {"A": "Judge sanctions only by changes in reported international trade volume.", "B": "Measure only changes in national and local government spending.", "C": "Ignore the political objective officially stated for the sanctions.", "D": "Evaluate direct losses, adaptation, and political behavior separately."},
    "l013_q2": {"A": "A valid lunch ticket.", "B": "A bottle of water.", "C": "A fully charged school computer.", "D": "A portable musical instrument."},
    "zh_r005_q3": {"A": "The participation fee will increase for every registered person", "B": "The entire course registration process will be canceled", "C": "The class will move to an online-only format", "D": "An extra Sunday afternoon class will be added"},
    "zh_r009_q1": {"A": "It counts too many different municipal office buildings", "B": "It may ignore people who cannot use the platform", "C": "It focuses only on the salaries of government employees", "D": "It prevents residents from submitting any online application"},
    "zh_r009_q3": {"A": "Every public service removes all in-person staff positions", "B": "All local residents must purchase completely new mobile phones", "C": "Public applications are sent overseas for final processing", "D": "People with different abilities can complete the same task"},
    "zh_r010_q1": {"A": "It completely excludes every visitor who comes on weekends", "B": "It counts only foreign tourists visiting the main exhibition", "C": "It does not show which groups gained access", "D": "It measures admission ticket prices using the wrong method"},
    "zh_r010_q3": {"A": "Identify the specific access barrier facing each visitor group before acting", "B": "Offer exactly the same ticket discount to every visitor group without exception", "C": "Replace all museum exhibits with new displays every week", "D": "Measure the program's success only through total admission revenue"},
    "zh_r011_q1": {"A": "Whether it produces many ceremonial statements at every annual summit", "B": "Whether all national leaders remain close personal friends over time", "C": "Whether the partnership avoids every difficult domestic election period", "D": "Whether it survives periods when members must bear costs"},
    "zh_r011_q3": {"A": "By whether serious disagreements between members ever occur at all", "B": "By whether disputes are managed without destroying long-term cooperation", "C": "By the total number of formal agreements and documents signed", "D": "By how quickly member governments replace their national leaders"},
    "zh_r012_q1": {"A": "They can hide unequal real-world outcomes", "B": "They cannot be published in official reports", "C": "They always reduce the survival rate of planted trees", "D": "They prevent cities from measuring local temperature differences"},
    "zh_r012_q2": {"A": "Trees may eventually stop every form of public transportation", "B": "Improved areas may become unaffordable to current residents", "C": "New green areas may eliminate all available rental housing", "D": "Official reports may prohibit low-income residents from entering parks"},
    "zh_r012_q3": {"A": "Only the average temperature across the entire city", "B": "The total number of environmental reports published each year", "C": "Health benefits and housing stability by community", "D": "Tourist purchases made near newly improved public parks"},
    "zh_l007_q1": {"A": "That almost nobody wanted any kind of home delivery service", "B": "That placing orders by telephone would always cost much less", "C": "That most young customers lived only in large cities", "D": "That channel choice would mainly depend on age"},
    "zh_l007_q3": {"A": "Permanently end every form of telephone ordering for all existing customers", "B": "Add phone staff and improve the app for slow networks", "C": "Serve only young customers who live in major cities", "D": "Close the entire delivery pilot program without further changes"},
    "zh_l008_q1": {"A": "Heavy rainfall washes accumulated road oil directly into the river", "B": "Factories release large amounts of hot water into the river daily", "C": "Large groups of fish block several narrow river tributaries", "D": "The new monitoring equipment releases chemicals into the water"},
    "zh_l009_q1": {"A": "That electronic books are available through modern public libraries", "B": "That libraries matter only as places for printed books", "C": "That students need quiet spaces for study and group work", "D": "That local communities organize regular cultural and educational events"},
    "zh_l010_q3": {"A": "At the beginning and end of each project", "B": "During every afternoon throughout the entire working week", "C": "Only during the project's initial employee hiring period", "D": "Throughout the project's entire middle planning and development stage"},
    "zh_l011_q1": {"A": "Autonomy requires ending every form of regional trade cooperation", "B": "Successful cooperation requires relying on one permanent supplier", "C": "Autonomy and cooperation respond to entirely unrelated policy concerns", "D": "Both can reduce dependence on a single source"},
    "zh_l011_q2": {"A": "Accepting routine costs to preserve backup capacity", "B": "Eliminating all emergency reserves maintained by member countries", "C": "Always choosing only the cheapest available regional supplier", "D": "Reducing every form of trade flow between regional partners"},
    "zh_l012_q1": {"A": "Accountability and error correction matter more than assuming perfection", "B": "Algorithms can never make errors in government decisions", "C": "Human decision-making systems contain no historical or personal bias", "D": "All automated computer code must remain secret from the public"},
    "zh_l012_q2": {"A": "Every submitted service application takes much longer to process", "B": "Existing bias may become harder for people to examine", "C": "All historical information immediately disappears from the automated system", "D": "No eligible applicants ever receive any allocated public services"},
    "zh_l012_q3": {"A": "Publishing technical computer code without any public explanation", "B": "Removing all forms of human oversight and institutional responsibility", "C": "People can understand decisions and use an appeal process", "D": "Keeping every automated decision permanently confidential from affected people"},
    "r001_q1": {"A": "Use the door on the right.", "B": "Enter through the door on the left.", "C": "Wait outside until noon.", "D": "Call the office manager."},
    "r002_q1": {"A": "Masha has a scheduled medical appointment this afternoon.", "B": "The school closes early today.", "C": "The family car is being repaired.", "D": "The writer will be late at work."},
    "r003_q5": {"A": "Doctors begin accepting patients without appointments.", "B": "The pharmacy reopens.", "C": "Repair work stops permanently.", "D": "The clinic is no longer open."},
    "r005_q1": {"A": "Construction work near the main central station.", "B": "A request from tourist agencies.", "C": "A reduction in fuel prices.", "D": "Complaints from residents of new neighborhoods."},
    "r005_q2": {"A": "How many passengers use the new trips.", "B": "How much the planned road construction will cost.", "C": "Whether drivers prefer new uniforms.", "D": "Whether residents move closer to work."},
    "r005_q3": {"A": "If all remaining late work shifts are eliminated.", "B": "If the added trips attract sufficient use.", "C": "If all routes become free.", "D": "If the city buys electric buses."},
    "r005_q4": {"A": "It is a driver training course.", "B": "It is the deadline for submitting resident complaints.", "C": "It is a trial used to evaluate demand.", "D": "It is a holiday transportation schedule."},
    "r007_q1": {"A": "Whether institutions survive conflicts of interest during crises.", "B": "Whether all national leaders maintain close personal relations.", "C": "How many declarations leaders sign at summits.", "D": "How quickly states expand membership."},
    "r008_q2": {"A": "Checking trees and removing fallen branches.", "B": "Building a completely new playground for children.", "C": "Moving sports equipment indoors.", "D": "Selling tickets at the gate."},
    "r008_q3": {"A": "The main sports zone.", "B": "The children's playground.", "C": "The parking garage.", "D": "The entire park."},
    "r008_q4": {"A": "A request seeking volunteer gardeners for the park.", "B": "A competition between sports teams.", "C": "A temporary closure and reopening schedule.", "D": "A new park construction project."},
    "r009_q1": {"A": "The office building closes at ten tonight.", "B": "Employees requested a later date.", "C": "The quarterly results are incomplete.", "D": "The director has a video conference."},
    "r010_q1": {"A": "Fewer telephone fraud cases among older residents.", "B": "A sharp rise in suspicious bank transfers.", "C": "Fewer meetings at social centers.", "D": "More bank branches in rural areas."},
    "r010_q3": {"A": "It was caused entirely by additional police arrests.", "B": "It came entirely from one new law.", "C": "It resulted from combining education and technical safeguards.", "D": "It happened because residents stopped using banks."},
    "r012_q3": {"A": "Funding too many new communication and automation technologies.", "B": "Protecting positions without addressing changing skill demands.", "C": "Collecting information from several indicators.", "D": "Reducing the number of routine operations."},
    "r012_q4": {"A": "It supplies a detailed historical example from an earlier period of automation.", "B": "It rejects the earlier discussion as irrelevant.", "C": "It proposes a multi-dimensional evaluation based on the identified problem.", "D": "It narrows the analysis back to job counts alone."},
    "l001_q2": {"A": "A passenger ticket refund.", "B": "A train departure location.", "C": "A delayed flight.", "D": "A station closure."},
    "l008_q1": {"A": "Strong winds will damage several major bridges.", "B": "Heavy fog will close airports.", "C": "Ice may form on the roads.", "D": "Flooding will block the highway."},
    "l008_q2": {"A": "Stop all driving until tomorrow morning.", "B": "Turn on emergency sirens.", "C": "Use only public transportation.", "D": "Slow down and keep distance."},
    "l009_q2": {"A": "A company celebration begins at noon.", "B": "The main first-floor conference room is being repainted.", "C": "Ventilation will be inspected on the second floor.", "D": "The sales department is closing permanently."},
    "l010_q2": {"A": "Ward availability is never considered.", "B": "The medical team still makes the final decision.", "C": "The system operates only outside the hospital building.", "D": "Patients select all surgery times themselves."},
    "l011_q1": {"A": "The city received fewer than ten usable public proposals.", "B": "Most comments opposed building any square.", "C": "Internet comments cannot be read by officials.", "D": "Some affected groups participated much less than others."},
    "l012_q1": {"A": "Political leaders immediately change their stated policy positions.", "B": "Economic adaptation and political outcomes can move differently.", "C": "Sanctions produce no direct economic losses.", "D": "Trade data are never available to governments."},
    "l014_q1": {"A": "No customers used the newly introduced delivery service.", "B": "The mobile application failed completely.", "C": "Deliveries occurred every day.", "D": "Telephone ordering was more popular than expected."},
    "l015_q2": {"A": "Residents are required to buy every book.", "B": "Printed books are no longer counted in official library statistics.", "C": "People may be using libraries for other valuable functions.", "D": "Digital services are available only to staff."},
    "zh_r001_q3": {"A": "Advertising a newly published book", "B": "Requesting volunteers", "C": "Changing an address", "D": "Giving today's closing time"},
    "zh_r002_q2": {"A": "At the train station", "B": "At a nearby store", "C": "At the original sender's home address", "D": "At the first-floor front desk"},
    "zh_r003_q1": {"A": "Because the regular bus driver is ill", "B": "Because of heavy snow", "C": "Because the bus is full", "D": "Because the road is under construction"},
    "zh_r003_q2": {"A": "People's Square", "B": "The nearby airport", "C": "The university", "D": "The hospital"},
    "zh_r004_q1": {"A": "Its starting time", "B": "Its planned topic", "C": "Its location", "D": "Its participants"},
    "zh_r004_q2": {"A": "Their vacation requests", "B": "Last month's sales data", "C": "A customer list", "D": "Their complete budget for next year"},
    "zh_r004_q3": {"A": "To publish the complete report on a public website", "B": "To send it to customers", "C": "To include it in the meeting materials", "D": "To calculate employee leave"},
    "zh_r005_q2": {"A": "Basic computer repair and software coding", "B": "Photography and video editing", "C": "Online registration and mobile payment", "D": "English and calligraphy"},
    "zh_r006_q3": {"A": "A city-hospital appointment slip", "B": "A cash payment", "C": "A personal home medical testing device", "D": "A train ticket"},
    "zh_r011_q2": {"A": "Personnel changes can weaken the mechanism", "B": "They make formal agreements too visible to the public", "C": "They eliminate economic interests", "D": "They prevent any security discussion"},
    "zh_l006_q1": {"A": "To sell all harvested vegetables for profit", "B": "To replace the sports field", "C": "For science learning and community giving", "D": "To train professional farmers"},
    "zh_l006_q2": {"A": "Local restaurant customers", "B": "School athletes", "C": "City officials", "D": "Older people nearby"},
    "zh_l006_q3": {"A": "Younger students now participate monthly", "B": "The community garden recently moved entirely indoors", "C": "Science classes were canceled", "D": "Only teachers may enter"},
    "zh_l007_q2": {"A": "Customers in areas with unstable internet", "B": "Only current employees of the delivery company", "C": "Only elderly city residents", "D": "People with no food order"},
    "zh_l009_q2": {"A": "A complete loss of the library's public value", "B": "A ban on community events", "C": "A change in how people use libraries", "D": "An increase in book prices"},
    "zh_l009_q3": {"A": "It counts some digital books more than once", "B": "It measures building size", "C": "It excludes all students", "D": "It misses several other public functions"},
    "zh_l010_q2": {"A": "Everyone should always complete every task from home", "B": "Only managers choose locations", "C": "Video meetings should be banned", "D": "Work setting should match the project stage"},
    "zh_l011_q3": {"A": "Only by continued growth in total regional trade volume", "B": "By whether it provides options under pressure", "C": "By the number of public speeches", "D": "By complete domestic production"},
}


def rewrite_jsonl(path: Path) -> int:
    records = []
    changed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("kind") == "question":
            question_id = str((record.get("data") or {}).get("id") or "")
            if question_id in CHOICE_REWRITES:
                record["data"]["choices"] = CHOICE_REWRITES[question_id]
                changed += 1
        records.append(record)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return changed


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    total = rewrite_jsonl(root / "data/starter_items.jsonl")
    total += rewrite_jsonl(root / "data/mandarin_starter_items.jsonl")
    print(f"Rewrote {total} starter-bank answer sets.")

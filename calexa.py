import pprint
import json
from datetime import datetime
import caldav
import urllib3
from caldav.elements import dav, cdav
from ics import Calendar
from flask import Flask
from flask_ask import Ask, statement
from datetime import timedelta

app = Flask(__name__)
ask = Ask(app, '/')

# read configuration
with open('./config.json') as json_data_file:
	config = json.load(json_data_file)

# open log files
#f = open('./calexa.log', 'a+')
def log(msg):
#	global f
#	f.write(msg)
#	f.flush()
	print(msg)

def connectCalendar():
	global config

	client = caldav.DAVClient(config["url"], username=config["username"], password=config["password"])
	principal = client.principal()
	calendars = principal.calendars()

	return sorted(calendars,key=lambda calendar: str(calendar.url))

def getCalDavEvents(begin, end):
	calendars = connectCalendar()
	speech_text = ""

	if (len(calendars) <= 0):
		speech_text = "  ich konnte mich leider nicht mit dem Kalender verbinden\n"
		log("ERROR: " + speech_text)
	else:
		eventList = []
		flatten = lambda l: [item for sublist in l for item in sublist]

		log("  gefundene Kalender: " + str(len(calendars)) + "\n")
		i = 0
		for calendar in calendars:
			log("	[" + str(i + 1) + "]: " + str(calendar))
			results = calendar.date_search(begin, end)

			log("  -> " + str(len(results)) + " Termine \n")
			if len(results) > 0:
				eventList = eventList + flatten([Calendar(event._data).events for event in results])
			i = i + 1

		if (len(eventList) <= 0):
			speech_text = "Es sind keine Termine eingetragen"
		else:
			sortedEventList = sorted(eventList,key=lambda icsEvent: icsEvent.begin)

#			pp = pprint.PrettyPrinter(indent=4)
#			pp.pprint(sortedEventList)

			speech_text = "<speak>\n"
			speech_text += '  Es sind folgende Termine auf dem Kalender:\n'
			for icsEvent in sortedEventList:
				speech_text += '  <break time="1s"/> ' + icsEvent.begin.humanize(locale='de') + " ist " + icsEvent.name + '.\n'
			speech_text += "</speak>"

	return speech_text

#@ask.intent('GetTodayEventsIntent')
#def getTodayEvents():
#	speech_text = getCalDavEvents(datetime.now(), datetime.now() + timedelta(days=1))
#	print(speech_text)
#	return statement(speech_text).simple_card('Kalendertermine', speech_text)

@ask.intent('GetEventsIntent', convert={ 'date': 'date', 'enddate': 'date' })
def getDateEvents(date, enddate):
	log("Reading events!\n")
	log("  date (from user): " + str(date) + " " + str(type(date)) + "\n")
	log("  enddate (from user): " + str(enddate) + " " + str(type(enddate)) + "\n")

	# in case that default "enddate" does not comply to "date",
	# the enddate is set to end of the day of "date"
	if date==None:
		date=datetime.now()

	if enddate==None or date>=enddate:
		enddate = datetime(date.year, date.month, date.day + 1)

	log("  date: " + str(date) + "\n")
	log("  endDate: " + str(enddate) + "\n")

	speech_text = getCalDavEvents(date, enddate)
	log("  text: " + speech_text + "\n")

	return statement(speech_text).simple_card('Kalendertermine', speech_text)

# We do have a minor problem here. There is no timezone information in the date/time objects...
# ... we assume the server's timezone, but it could be that this is wrong. So if created events are off by some hour(s)
# this is the reason. If someone wants to provide a simple PR then this would be great :-)
@ask.intent('SetEventIntent', convert={'date': 'date', 'time':'time', 'duration' : 'timedelta'})
def setEvent(date, time, duration, eventtype, location):
	log("Creating event!\n");
	log("  date (from user): " + str(date) + "\n")
	log("  time (from user): " + str(time) + "\n")
	log("  duration (from user): " + str(duration) + "\n")
	log("  eventtype (from user): " + str(eventtype) + "\n")
	log("  location (from user): " + str(location) + "\n")
	speech_text = "Termin konnte nicht eingetragen werden!"

	if eventtype==None:
		eventtype='Besprechung'

	if date==None:
		date = datetime.today()

	if duration==None:
		duration = timedelta(hours=1)

	d = datetime.combine(date,time)

	creationDate = datetime.now().strftime("%Y%m%dT%H%M%S")
	startDate = d.strftime("%Y%m%dT%H%M%S")
	endDate = (d + duration).strftime("%Y%m%dT%H%M%S")

	log("  startDate: " + str(startDate) + "\n")
	log("  endDate: " + str(endDate) + "\n")

	vcal = "BEGIN:VCALENDAR"+"\n"
	vcal += "VERSION:2.0"+"\n"
	vcal += "PRODID:-//Example Corp.//CalDAV Client//EN"+"\n"
	vcal += "BEGIN:VEVENT"+"\n"
	vcal += "UID:1234567890"+"\n"
	vcal += "DTSTAMP:" + creationDate +"\n"
	vcal += "DTSTART:" + startDate +"\n"
	vcal += "DTEND:" + endDate +"\n"
	vcal += "SUMMARY:" + eventtype + "\n"
	vcal += "END:VEVENT"+"\n"
	vcal += "END:VCALENDAR"

	log("  entry: " + vcal + "\n")

	calendars = connectCalendar()
	if (len(calendars) <= 0):
		speech_text = "Ich konnte mich leider nicht mit dem Kalender verbinden"
		log("ERROR: " + speech_text + "\n")
	else:
		# This could be sooo much easier if we had something like "if (calendar.isReadOnly())"
		i = 0;
		log("  gefundene Kalender: #" + str(len(calendars)) + "\n")
		for calendar in calendars:
			log("  [" + str(i + 1) + "]: " + str(calendar) + "\n")
			try:
				event = calendar.add_event(vcal)
				speech_text = "Termin wurde eingetragen!"

				# Everything worked out well and event has been entered into one calendar -> we do not have to try other calendars and therefore skip the loop
				break
			except Exception as te:
				if (i >= len(calendars)):
					speech_text = "Ich konnte in keinen Kalender schreiben"
					log("ERROR: " + speech_text + "\n")
					log("ERROR: " + str(te) + "\n")
					pass
				else:
					log("  konnte nicht in Kalender schreiben: " + str(calendar) + ". Versuche nächsten Kalender...\n")
					# Try using the next calendar... we will fail when the event could not be added to any calendar
					i = i + 1

	log("  text: " + speech_text + "\n")
	return statement(speech_text).simple_card('Kalendertermine', speech_text)

#print getTodayEvents()
if __name__ == '__main__':
	app.run(host="0.0.0.0", port=config["calexaPort"])

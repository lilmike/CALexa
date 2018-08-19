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

# open log files
#f = open('./log/calexa.log', 'a')
#fe = open('./log/calexa_error.log', 'a')

# read configuration
with open('./config.json') as json_data_file:
	config = json.load(json_data_file)

def connectCalendar():
	global config

	client = caldav.DAVClient(config["url"], username=config["username"], password=config["password"])
	principal = client.principal()
	return principal.calendars()

def getCalDavEvents(begin, end):
#	global f, fe
	calendars = connectCalendar()
	speech_text = ""

	if (len(calendars) <= 0):
		speech_text = "  ich konnte mich leider nicht mit dem Kalender verbinden\n"
#		fe.write(speech_text)
#		fe.flush()
	else:
		eventList = []
		flatten = lambda l: [item for sublist in l for item in sublist]

#		f.write("  gefundene Kalender: " + str(len(calendars)) + "\n")
		i = 0
		for calendar in calendars:
#			f.write("	[" + str(i + 1) + "]: " + str(calendar))
			results = calendar.date_search(begin, end)

#			f.write("  -> " + str(len(results)) + " Termine \n")
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
#	global f, fe

#	f.write("Reading events!\n")
#	f.write("  date (from user): " + str(date) + " " + str(type(date)) + "\n")
#	f.write("  enddate (from user): " + str(enddate) + " " + str(type(enddate)) + "\n")

	# in case that default "enddate" does not comply to "date",
	# the enddate is set to end of the day of "date"
	if date==None:
		date=datetime.now()

	if enddate==None or date>=enddate:
		enddate = datetime(date.year, date.month, date.day+1)

#	f.write("  date: " + str(date) + "\n")
#	f.write("  endDate: " + str(enddate) + "\n")

	speech_text = getCalDavEvents(date, enddate)
#	f.write("  text: " + speech_text + "\n")
#	f.flush()

	return statement(speech_text).simple_card('Kalendertermine', speech_text)

@ask.intent('SetEventIntent', convert={'date': 'date', 'time':'time', 'duration' : 'timedelta'})
def setEvent(date, time, duration, eventtype, location):
#	global f, fe

#	f.write("Creating net event!\n");
#	f.write("  date: " + date + "\n")
#	f.write("  time: " + time + "\n")
#	f.write("  duration: " + duration + "\n")
	speech_text = "Termin konnte nicht eingetragen werden!"

	try:
		if date==None:
			date = datetime.today()

		if duration==None:
			duration = timedelta(hours=1)

		d = datetime.combine(date,time)

		creationDate = datetime.now().strftime("%Y%m%dT%H%M%SZ")
		startDate = d.strftime("%Y%m%dT%H%M%SZ")
		endDate = (d + duration).strftime("%Y%m%dT%H%M%SZ")

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

#		f.write("  entry: " + vcal + "\n")

		calendars = connectCalendar()

		if len(calendars) > 0:
			calendar = calendars[0]
			event = calendar.add_event(vcal)
			speech_text = "Termin wurde eingetragen!"

	except TypeError as te:
#		fe.write("  error: " + te + "\n")
#		fe.flush()
		pass

#	f.write("  text: " + speech_text + "\n")
#	f.flush()

	return statement(speech_text).simple_card('Kalendertermine', speech_text)

#print getTodayEvents()
if __name__ == '__main__':
	app.run(host="0.0.0.0", port=config["calexaPort"])

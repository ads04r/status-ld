#!/usr/bin/python3

import json, os, sys, urllib, re, psutil, urllib.parse, requests

def publish(import_url, token, data):

	component_url = urllib.parse.urlsplit(import_url)

	url = str(component_url.scheme) + "://" + str(component_url.netloc) + "/import?" + urllib.parse.urlencode({'parent': import_url, 'overwrite-outside': 'true'})
	headers = {
		"Accept": "application/json-ad",
		"Authorization": "Bearer " + token
	}
	try:
		with requests.post(url, timeout=10, headers=headers, data=json.dumps(data)) as r:
			return(r.json())
	except:
		return {}

def blank_property(uri, type, name='', description=''):

	ret = {
	  "@id": uri,
	  "https://atomicdata.dev/properties/datatype": type,
	  "https://atomicdata.dev/properties/description": description,
	  "https://atomicdata.dev/properties/isA": [
	    "https://atomicdata.dev/classes/Property"
	  ],
	  "https://atomicdata.dev/properties/isDynamic": False,
	  "https://atomicdata.dev/properties/isLocked": False,
	  "https://atomicdata.dev/properties/shortname": name
	}
	return ret

def build_ontology(data):

	ret = []
	for k, v in data.items():
		if not k.startswith(prop):
			continue
		uri = k
		name = uri.replace('#', '/').split('/')[-1]
		type = 'string'
		if isinstance(v, list):
			type = 'resourceArray'
		if isinstance(v, int):
			type = 'integer'
		if isinstance(v, float):
			type = 'float'
		if isinstance(v, bool):
			type = 'boolean'
		if type == 'string':
			if '://' in v:
				type = 'resource'
		ret.append(blank_property(uri, "https://atomicdata.dev/datatypes/" + type, name))
	return ret

def network():

	c = psutil.net_io_counters()
	ret = {}
	ret[prop + 'bytes-sent'] = c.bytes_sent
	ret[prop + 'bytes-recv'] = c.bytes_recv
	ret[prop + 'packets-sent'] = c.packets_sent
	ret[prop + 'packets-recv'] = c.packets_recv
	ret[prop + 'errin'] = c.errin
	ret[prop + 'errout'] = c.errout
	return ret

def uptime():

	cmd = "cat /proc/uptime | sed 's/[^0-9].*$//'"
	ret = 0
	with os.popen(cmd) as sp:
		ret = int(sp.read().strip())
	return ret

def getremotejson(url):

	operUrl = urllib.request.urlopen(url)
	if(operUrl.getcode()==200):
		data = json.loads(operUrl.read())
	else:
		data = {}
	return data

def backupcheck():

	path = '/home/pi/backups'
	dumps_path = os.path.join(path, 'dumps')
	bu_path = os.path.join(path, 'bulk-uploads')
	data = {prop + 'last-backup': '', prop + 'files': []}

	dates = []
	for file in os.listdir(dumps_path):
		if not file.endswith('.gz'):
			continue
		for ds in re.findall(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', file):
			dates.append(ds)
	dates.sort(reverse=True)
	data[prop + 'last-backup'] = dates[0]
	for file in os.listdir(dumps_path):
		if not data[prop + 'last-backup'] in file:
			continue
		data[prop + 'files'].append(file)

	return data

def power():

	cmd = "vcgencmd get_throttled | sed 's/^throttled=//'"
	with os.popen(cmd) as sp:
		data = int(sp.read().strip(), 0)
	ret = []
	for i in range(0, 19):
		ovr = pow(2, (18 - i))
		if data>=ovr:
			data = data - ovr
			ret.append(True)
		else:
			ret.append(False)
	return ret

def temperature():

	cmd = "vcgencmd measure_temp | sed 's/^temp=//' | sed \"s/'/|/\""
	with os.popen(cmd) as sp:
		data = sp.read().strip().split("|")
	ret = {'value': float(data[0]), 'unit': data[1]}
	return ret

def diskuse():

	cmd = "df | sed 's/  */|/g'"
	headers = []
	data = []
	with os.popen(cmd) as sp:
		for l in sp.read().split('\n'):
			ll = l.split('|')
			if len(headers) == 0:
				headers = ll
				continue
			item = {}
			for i in range(0, len(ll)):
				item[headers[i]] = ll[i]
			if len(item) > 1:
				data.append(item)

	ret = []
	for item in data:
		if not ('Mounted' in item):
			continue
		if not ('Used' in item):
			continue
		if not ('Available' in item):
			continue
		ret.append([item['Mounted'], int(item['Available']), int(item['Used'])])

	return ret

base_path = os.path.abspath(os.path.dirname(sys.argv[0]))
config_file = os.path.join(base_path, 'config.json')

with open(config_file) as fp:
	config = json.load(fp)

ontology_uri = config['ontology']
base_uri = config['database'] + '/'

prop = ontology_uri + 'properties/'
cls = ontology_uri + 'class/'


data = {
	"@id": base_uri + config['hostname'],
	"https://atomicdata.dev/properties/isA": [cls + "host"],
	prop + "parent": base_uri.rstrip('/'),
	"https://atomicdata.dev/properties/name": config['hostname'],
}
data[prop + 'uptime'] = uptime()

#data[prop + 'message'] = 'Status script ran OK.'
#data[prop + 'disks'] = diskuse()

p = power()
data[prop + 'is-under-voltage'] = p[0]
data[prop + 'is-freq-capped'] = p[1]
data[prop + 'is-throttled'] = p[2]
data[prop + 'is-temp-limit'] = p[3]
data[prop + 'was-under-voltage'] = p[4]
data[prop + 'was-freq-capped'] = p[5]
data[prop + 'was-throttled'] = p[6]
data[prop + 'was-temp-limit'] = p[7]

for k, v in network().items():
	data[k] = v
for k, v in temperature().items():
	data[prop + 'temperature-' + k] = v
#for k, v in backupcheck().items():
#       data[k] = v
if 'apis' in config:
	for kk in config['apis'].keys():
		k = str(kk)
		v = getremotejson(config['apis'][k])
		if isinstance(v, dict):
			for kk, vv in v.items():
				if isinstance(vv, dict):
					continue
				data[(prop + k + '-' + kk.replace('_', '-')).strip().lower()] = vv
			continue
		data[prop + k] = v

publish(config['database'], config['token'], [data])


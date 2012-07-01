import logging
import math
import os
try: import simplejson as json
except ImportError: import json

from google.appengine.ext.webapp import template
from google.appengine.ext import db

from model import SquaredarUser
from abstract_app import AbstractApp


class Squaredar(AbstractApp):
  MOVING_AVG_WINDOW = 10
  
  IS_TRAVELING = False
  
  def contentGet(self, client, content_info):
    alerts_json = json.loads(content_info.content)
    path = os.path.join(os.path.dirname(__file__), 'reply.html')
    self.response.out.write(template.render(path, alerts_json))
    return

  def checkinTaskQueue(self, client, checkin_json):
    venue_json = checkin_json['venue']
    lat = venue_json['location']['lat']
    lng = venue_json['location']['lng']
    latlng = lat+','+lng

    request = SquaredarUser.all().filter('fs_id =', checkin_json['user']['id'])
    sq_user = request.get()
    if not sq_user:
      sq_user = SquaredarUser()
      sq_user.fs_id = checkin_json['user']['id']
      sq_user.history = []

    trim_loc = self.trimLocation(venue_json['location'])
    trim_loc['lat'] = int(math.floor(float(lat)))
    trim_loc['lng'] = int(math.floor(float(lng)))

    entry = { 'timestamp' : checkin_json['createdAt'],
              'location' : trim_loc
            }

    for old_entry in sq_user.history:
      old_entry = json.loads(old_entry)
      old_location = old_entry['location']
      location = entry['location']
      if self.geoDistance(old_location, location) > 2:
        logging.info('User is traveling from %s to %s' % 
                     (self.makeRegionName(old_location, location),
                      self.makeRegionName(location)))
        self.IS_TRAVELING = True
        break
    
    sq_user.history.insert(0, db.Text(json.dumps(entry)))
    if len(sq_user.history) > self.MOVING_AVG_WINDOW:
      sq_user.history.pop()
    
    recent_checkins = client.checkins.recent(params={'ll': latlng})
    if not sq_user.friends:
      sq_user.friends = "{}"
    friend_map = json.loads(sq_user.friends)

    close_friend_tuples = []

    # Find friends who are closer than normal
    for friend_checkin in recent_checkins['recent']:
      friend_user = friend_checkin['user']
      if 'type' in friend_user and friend_user['type'] == 'page':
        # Skip brands
        continue
      if 'venue' not in friend_checkin:
        # Damn shouts
        continue
      distance = friend_checkin['distance']
      friend_id = str(friend_checkin['user']['id'])
      if friend_id in friend_map:
        friend = friend_map[friend_id]
        avg_distance = friend['avg_distance']
        if distance < (avg_distance / 100):
          close_friend_tuples.append([friend, friend_checkin])
    
    user_id = checkin_json['user']['id']
    friend_alerts = []
    alerts_json = self.makeReply(client, close_friend_tuples, checkin_json)
    if alerts_json:
      self.sendReply(client, alerts_json, checkin_json)
      for alert in alerts_json['alerts']:
        friend_alerts.append(alert['friend_id'])

    # Update friend distances
    for friend_checkin in recent_checkins['recent']:
      if 'venue' not in friend_checkin:
        # Shout (no venue)
        continue
      friend_user = friend_checkin['user']
      if 'type' in friend_user and friend_user['type'] == 'page':
        # Skip brands
        continue
      friend_id = str(friend_user['id'])
      # No point keeping track of ourselves
      if friend_id == user_id:
        continue
      alerted = (friend_id in friend_alerts)
      spotting = self.makeSpotting(friend_checkin, checkin_json, alerted)

      # Friend has been spotted before
      if friend_id in friend_map:
        friend = friend_map[friend_id]
        spottings = friend['spottings']
        last_spotting_ts = spottings[0]['timestamp']
        if last_spotting_ts == friend_checkin['createdAt']:
          # Already recorded this particular spotting
          # If we alerted this time, remove the old spotting to be replaced.
          # Otherwise, skip the update.
          if alerted:
            spottings.pop(0)
          else:
            continue
        spottings.insert(0, spotting)
        if len(spottings) > self.MOVING_AVG_WINDOW:
          spottings.pop()
        friend['spottings'] = spottings
        friend['avg_distance'] = self.calculateAverageDistance(friend)
        friend_map[friend_id] = friend
#        friend.put()
      else:
        friend = self.makeFriend(friend_checkin, checkin_json)
        friend['spottings'] = [ spotting ]
        friend_map[friend_id] = friend
    sq_user.friends = json.dumps(friend_map)

    # Save changes
    sq_user.put()


  def geoDistance(self, location_a, location_b):
    lat_a = location_a['lat']
    lat_b = location_b['lat']
    lng_a = location_a['lng']
    lng_b = location_b['lng']
    return math.sqrt(pow(lat_a - lat_b, 2) + pow(lng_a - lng_b, 2))

  def trimLocation(self, input):
    output = {}
    if 'city' in input:
      output['city'] = input['city']
    if 'state' in input:
      output['state'] = input['state']
    if 'country' in input:
      output['country'] = input['country']
    return output

  def makeReply(self, client, friend_tuples, user_checkin):
    if len(friend_tuples) == 0:
      return

    names = []
    justifications = []
    content_array = []
    for (friend, friend_checkin) in friend_tuples:
      if self.shouldReply(friend, friend_checkin, user_checkin):
        names.append(friend.name)
        msg = self.makeJustification(friend, friend_checkin, user_checkin)
        justifications.append(msg)
        friend_content = { 'checkin_id' : friend_checkin['id'],
                           'justification' : msg,
                           'friend_id' : friend_checkin['user']['id'],
                           'checkin_ts' : friend_checkin['createdAt']}
        content_array.append(friend_content)
    
    msg = ''
    
    if len(names) == 0:
      return
    elif len(names) == 1:
      msg = justifications[0]
    elif len(names) == 2:
      name_str = ' and '.join(names)
      msg = '%s are nearby' % name_str
    else:
      name_str = ', '.join(names[:2])
      if len(names) > 2:
        plural = 's' if len(names) > 3 else ''
        name_str += " and %s other friend%s" % ((len(names) - 2), plural)
      msg = '%s are nearby' % name_str

    content_json = { 'createdAt' : user_checkin['createdAt'],
                     'message' : msg,
                     'alerts' : content_array }
    return content_json


  def sendReply(self, client, content_json, checkin_json):
    content = json.dumps(content_json)
    encoded_message = content_json['message'].encode('utf-8')
    return self.makeContentInfo(checkin_json=checkin_json,
                                content=content,
                                text=encoded_message,
                                reply=True)
     
    
  def shouldReply(self, friend, friend_checkin, user_checkin):
    # TODO(ak): Should check if it's replied you in the past.
    # Or maybe see if the person has been "near" for a while?
    current_venue_id = user_checkin['venue']['id']
    friend_venue_id = friend_checkin['venue']['id']
    if current_venue_id == friend_venue_id:
      # You're already together! No need to reply
      return False

    current_time = user_checkin['createdAt']

    # If you've checked in to the same venue as them within the last 4 days,
    # don't bother replying. This is to avoid the co-worker weekend trip issue.
    for spotting in friend.spottings:
      spotting_json = json.loads(spotting)
      if spotting_json['same_venue']:
        spotting_age = current_time - spotting_json['timestamp']
        if spotting_age < 5 * 86400:
          return False
      if 'alerted' in spotting_json and spotting_json['alerted']:
        return False
        
    friend_time = friend_checkin['createdAt']
    
    # If you're traveling, you don't care about the following checks.
    if self.IS_TRAVELING:
      return True
    
    # Check if it's a generally close friend with a stale check-in.
    if friend.avg_distance < 100000 and (current_time - friend_time) > 10800:
      return False

    return True
      
  def makeJustification(self, friend, friend_checkin, user_checkin):
    friend_distance = friend_checkin['distance']
    friend_venue = friend_checkin['venue']
    user_venue = user_checkin['venue']
    region_name = self.makeRegionName(friend_venue['location'],
                                      user_venue['location'])
    message = ''
    if friend_distance < 100:
      message = '%s is super nearby @ %s' % (friend.name, friend_venue['name'])
    elif friend_distance < 1000:
      message = '%s is nearby @ %s' % (friend.name, friend_venue['name'])
    elif friend_distance < 10000:
      message = '%s is in town (last seen @ %s)' % (friend.name, friend_venue['name'])
    elif friend_distance < 100000:
      message = '%s is in %s (last seen @ %s)' % (friend.name, region_name, friend_venue['name'])
    elif friend_distance < 1000000:
      message = '%s is in %s' % (friend.name, region_name, friend_venue['name'])
    
    # Where were they perviously? Pick the furthest away place they were
    # over half of the moving window.
    old_distance = 0
    old_region_name = ''
    for spotting in friend.spottings[0:self.MOVING_AVG_WINDOW/2]:
      spotting_json = json.loads(spotting)
      if spotting_json['distance'] > old_distance:
        old_distance = spotting_json['distance']
        old_region_name = spotting_json['region_name']

    if not self.IS_TRAVELING:
      if old_region_name and old_region_name != region_name:
        message += ', back from %s' % old_region_name
    
    return message
      
  
  def makeSpotting(self, friend_checkin, user_checkin, alerted=False):
    location_json = friend_checkin['venue']['location']
    user_venue_id = user_checkin['venue']['id']
    user_location_json = user_checkin['venue']['location']
    friend_venue_id = friend_checkin['venue']['id']

    spotting = { 'distance' : friend_checkin['distance'],
                 'region_name' : self.makeRegionName(location_json,
                                                     user_location_json),
                 'timestamp' : friend_checkin['createdAt'],
                 'same_venue' : (user_venue_id == friend_venue_id),
                 'alerted' : alerted,
                 'location' : self.trimLocation(location_json)
                }
    return spotting
  
  def makeRegionName(self, location_json, relative_location_json=None):
    regions = []
    if relative_location_json:
      if self.hasDifferent('city', location_json, relative_location_json):
        regions.append(location_json['city'])
      if self.hasDifferent('state', location_json, relative_location_json):
        regions.append(location_json['state'])
      if self.hasDifferent('country', location_json, relative_location_json):
        regions.append(location_json['country'])
    else:
      if 'city' in location_json:
        regions.append(location_json['city'])
      elif 'state' in location_json:
        regions.append('somewhere in %s' % location_json['state'])
      elif 'country' in location_json:
        regions.append('somewhere in %s' % location_json['country'])
      else:
        regions.append('somewhere')
    return ', '.join(regions)
    
  def hasDifferent(self, field, target, relative):
    if field in target:
      if field not in relative or target[field] != relative[field]:
        return True
    return False
      
  def makeFriend(self, friend_checkin, user_checkin):
    friend = {}
    friend_json = friend_checkin['user']
    friend['id'] = friend_json['id']
    name = ""
    if 'firstName' in friend_json:
      name = friend_json['firstName']
    if 'lastName' in friend_json:
      name += ' ' + friend_json['lastName']
    friend['name'] = name
    friend['spottings'] = []
    friend['avg_distance'] = self.calculateAverageDistance(friend)
    return friend

  def calculateAverageDistance(self, friend):
    avg_distance = 0
    for spotting in friend['spottings']:
      avg_distance += spotting['distance']
    avg_distance = avg_distance / self.MOVING_AVG_WINDOW
    return avg_distance

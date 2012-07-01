from google.appengine.ext import db

class Friend(db.Model):
  """A friend of the user"""
  user_fs_id = db.StringProperty()
  friend_fs_id = db.StringProperty()
  name = db.TextProperty()
  spottings = db.ListProperty(db.Text)
  avg_distance = db.IntegerProperty()

class SquaredarUser(db.Model):
  """A user of Squaredar"""
  fs_id = db.StringProperty()
  history = db.ListProperty(db.Text)
  friends = db.TextProperty(db.Text)
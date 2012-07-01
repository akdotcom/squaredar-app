# Don't import anything that imports CONFIG here, the circular dependency will not work.
# Instead, import after the definition of CONFIG.

CONFIG = {
  # foursquare server to use. You probably don't need to change this.
  'foursquare_server':'https://foursquare.com',
  # The server name for local_dev mode. Make sure the port matches what you use.
  'local_server': 'http://localhost:8092',
  # Server name for your deployed AppEngine instance
  'prod_server': 'https://squaredar.appspot.com',
  # OAuth client ID. Must match what you set at https://foursquare.com/oauth.
  'client_id': 'L1QEJFHM1PSKOBTXJSWC3XRB0NQ1Y5PYELCGKTJ01QE2AFG3',
  # OAuth callback/redirect URI. Must match what you set at https://foursquare.com/oauth.
  'redirect_uri': '%s/oauth', # (server)
  # Format string to serve URL content out of. Not necessarily required.
  'content_uri': '%s/content?content_id=%s', # (server, content_id)
  # The foursquare API version string to pass. See: https://developer.foursquare.com/overview/versioning
  'api_version': '20120608',
  # A name for the hompage and titles.
  'site_name': 'Squaredar',
  # A description for the home page
  'site_description': 'Find out when far away friends are finally nearby',
  # If true, we use local_server, and log actions instead of POSTing to foursquare
  # Be sure to set this to false when you actually want to deploy.
  'local_dev': False,
  # AppEngine debug mode
  'debug': True,
  # These can either be a path (on this server), or an external URI
  'auth_success_uri_desktop': '/static/allset.html',
  'auth_success_uri_mobile': '/static/allset.html',
  'auth_denied_uri': '/',
  # Application Level Configuration
  # Feel free to add new config parameters here...
}

# Replace 'None' with the class object of your app. It must inherit from the
# provided AbstractApp class.
from squaredar.squaredar import Squaredar

APP_CLASS = Squaredar

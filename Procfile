# vim: ft=ruby

# Run any new migrations each time a release is created
release: python manage.py migrate

# Single web process
web: gunicorn pelotourney.wsgi

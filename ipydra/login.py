import os
import os.path
import sh
import subprocess
import shutil

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask.ext.wtf import Form
from flask.ext.wtf import PasswordField
from flask.ext.wtf import TextField

from ipydra import db
from ipydra import models

bp = Blueprint('frontend', __name__)

class LoginForm(Form):
    username = TextField('Username')
    password = PasswordField('Password')

    def validate(self):
        from ipydra import bcrypt
        # first check password
        if not bcrypt.check_password_hash(
            '$2a$12$x3dxjmTasFhnxuK7n2ifu.GZIQV3tAM97YjHR5Yy/hGPuPGLhyd4C',
            self.password.data):
            return False
        if not self.username.data.isalnum():
            return False
        return True


@bp.route('/', methods=['GET', 'POST'])
def nbserver():
    from ipydra import ROOT_DIR
    from ipydra import NB_URL

    form = LoginForm(csrf_enabled=False)
    if form.validate_on_submit():
        username = str(form.username.data)
        ip_dir = '{0}/.ipython'.format(ROOT_DIR + username)
        # create user directories if they dont exist
        if not user_exists(username):
            create_user(username)
        # check if user already has a server running
        user = models.User.query.filter(models.User.username == username).first()
        if not user:
            port = 9499 + models.User.query.count() + 1
            # start server
            pid = run_server(ip_dir, port)
            user = models.User()
            user.username = username
            user.nbserver_port = port
            user.nbserver_pid = pid
            db.session.add(user)
            db.session.commit()
            # sleep to let the server start and listen
            sh.sleep(1)
        else:
            port = user.nbserver_port
        return redirect('{0}:{1}'.format(NB_URL, port))
    return render_template('login.jinja.html', form=form)

def run_server(ip_dir, port):
    """ Run a notebook server with a given ipython directory and port.
        Returns a PID.
    """
    pid = subprocess.Popen(['/home/ubuntu/repos/venv/bin/ipython',
                            'notebook',
                            '--profile=nbserver',
                            '--NotebookApp.port={0}'.format(port),
                            '--NotebookApp.ipython_dir={0}'.format(ip_dir)]).pid
    return pid

def user_exists(username):
    """ Check if user exists.
    """
    from ipydra import ROOT_DIR
    return os.path.exists('{0}{1}'.format(ROOT_DIR, username))

def create_user(username):
    """ Create a new user.
    """
    from ipydra import ROOT_DIR

    user_dir = '{0}{1}'.format(ROOT_DIR, username)
    ip_dir = '{0}/.ipython'.format(user_dir)
    log_file = '{0}/log'.format(ip_dir)
    conf_dir = '{0}/profile_nbserver'.format(ip_dir)
    nb_dir = '{0}/notebooks'.format(user_dir)
    data_dir = '{0}/data'.format(user_dir)

    os.makedirs(ip_dir)
    os.makedirs(conf_dir)
    os.makedirs(data_dir)
    sh.touch(log_file)

    # generate ssl cert

    # render config
    config = render_template('ipython_notebook_config.jinja.py',
                             username=username,
                             ip_dir=ip_dir,
                             nb_dir=nb_dir)
    config_file = open('{0}/ipython_notebook_config.py'.format(conf_dir), 'w')
    config_file.write(config)
    config_file.close()

    # copy data files over
    shutil.copytree('/home/ubuntu/repos/pycon2013/',
                    '{0}'.format(nb_dir))

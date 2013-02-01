import os, sys

from fabric.api import env, run, cd, sudo, put
from fabric.decorators import hosts


DEFAULTS = {
    'home': '/home/wsgi/srv/',
    'repo_name': 'formhub',
    }

DEPLOYMENTS = {
    'default': {
        'home': '/home/ubuntu/srv',
        'host_string': 'ubuntu@192.168.0.86',
        #'key_filename': os.path.expanduser('~/.ssh/id_rsa'),
        'project': 'formhub-srv'
    }
}


def run_in_virtualenv(command):
    d = {
        'activate': os.path.join(
            env.project_directory, 'project_env', 'bin', 'activate'),
        'command': command,
        }
    run('source %(activate)s && %(command)s' % d)


def check_key_filename(deployment_name):
    if DEPLOYMENTS[deployment_name].has_key('key_filename') and \
        not os.path.exists(DEPLOYMENTS[deployment_name]['key_filename']):
        print "Cannot find required permissions file: %s" % \
            DEPLOYMENTS[deployment_name]['key_filename']
        return False
    return True

def setup_env(deployment_name):
    env.update(DEFAULTS)
    env.update(DEPLOYMENTS[deployment_name])
    if not check_key_filename(deployment_name): sys.exit(1)
    env.project_directory = os.path.join(env.home, env.project)
    env.code_src = os.path.join(env.project_directory, env.repo_name)
    env.wsgi_config_file = os.path.join(
        env.project_directory, 'apache', 'environment.wsgi')
    env.pip_requirements_file = os.path.join(env.code_src, 'requirements.pip')


def deploy(deployment_name, branch='master'):
    setup_env(deployment_name)
    with cd(env.code_src):
        run("git fetch origin")
        run("git checkout origin/%s" % branch)
        run('find . -name "*.pyc" -exec rm -rf {} \;')
    # numpy pip install from requirments file fails
    run_in_virtualenv("pip install gunicorn")
    run_in_virtualenv("pip install numpy")
    run_in_virtualenv("pip install -r %s" % env.pip_requirements_file)
    with cd(env.code_src):
        run_in_virtualenv("python manage.py syncdb --noinput")
        run_in_virtualenv("python manage.py migrate")
        run_in_virtualenv("python manage.py collectstatic --noinput")


def server_reload_services(deployment_name):
    setup_env(deployment_name)
    run("sudo /etc/init.d/celeryd restart")
    run("sudo reload gunicorn-formhub")


def server_setup(deployment_name):
    setup_env(deployment_name)
    sudo("apt-get update")
    sudo("apt-get -y install python-software-properties")
    sudo("add-apt-repository -y ppa:apt-fast/stable")
    sudo("apt-get update")
    sudo("apt-get -y install apt-fast")
    sudo("test -f /tmp/apt-fast.lock && rm /tmp/apt-fast.lock || ls")
    sudo("apt-fast -y upgrade")
    sudo("apt-fast -y install default-jre gcc git python-dev")
    sudo(" apt-fast -y install python-virtualenv libjpeg-dev libfreetype6-dev zlib1g-dev "
        "rabbitmq-server nginx monit")
    sudo("apt-fast -y install mongodb")
    run("mkdir -p %s" % env.home)
    run('git clone git://github.com/modilabs/django_wsgi_deployer.git -bnginx deployer')
    with cd('deployer'):
        put('local.configs.yaml', 'local.configs.yaml')
        run('virtualenv --no-site-packages project_env')
        run('source project_env/bin/activate && pip install -r requirements.pip')
        run('source project_env/bin/activate && python deployer.py')


def server_config(deployment_name):
    setup_env(deployment_name)
    nginx_cfg = os.path.join(env.project_directory, 'nginx', 'site.conf')
    sudo("test -f /etc/nginx/sites-enabled/%(site_cfg)s.conf || "
        "ln -s %(nginx_cfg)s /etc/nginx/sites-enabled/%(site_cfg)s.conf" \
        % {'nginx_cfg':nginx_cfg, 'site_cfg': deployment_name})
    celeryd_file = os.path.join(env.project_directory, 'celery', 'celeryd')
    sudo("test -f /etc/init.d/celeryd || cp %s /etc/init.d/celeryd" % celeryd_file)
    sudo("chmod +x /etc/init.d/celeryd")
    gunicorn_start_script = os.path.join(
        env.project_directory, 'etc', 'init', 'gunicorn-formhub.conf')
    sudo("test -f /etc/init/gunicorn-formhub.conf || "
        "ln -s %s /etc/init/gunicorn-formhub.conf" % (gunicorn_start_script))
    celery_cfg = os.path.join(
        env.project_directory, 'etc', 'default', 'celeryd')
    sudo("cp %s /etc/default/celeryd" % (celery_cfg))
    gunicorn_shell_script = os.path.join(
        env.code_src, 'run_gunicorn.sh')
    sudo("chmod +x %s" % (gunicorn_shell_script))
    sudo("test -f /etc/init.d/gunicorn-formhub || "
        "ln -s /lib/init/upstart-job /etc/init.d/gunicorn-formhub")
    sudo('update-rc.d gunicorn-formhub defaults')
    sudo('update-rc.d celeryd defaults')
    sudo('initctl reload-configuration')
    sudo('service nginx restart')
    sudo('service celeryd start')
    sudo('start gunicorn-formhub')

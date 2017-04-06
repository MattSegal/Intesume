#!/usr/bin/env groovy

env.ENVIRONMENT_TYPE = 'PROD'
env.TARGET_NODE_ADDRESS = '192.241.240.97'
env.DOMAIN_NAME = 'intesume.com'
env.APP_NAME = 'intesume'

def WEBAPPS_DIR = '/var/webapps'
def DEPLOY_DIR = "${WEBAPPS_DIR}/intesume/app"
def VIRTUALENV_DIR = "${WEBAPPS_DIR}/${APP_NAME}"
def ZIP_FILE = "${APP_NAME}.tar.gz"

def clone_or_pull(directory, remote)
{
    sh ("""
    if [ ! -d ${directory}/.git ]
    then
        git clone ${remote} ${directory}
    else
        git -C ${directory} pull
    fi
    """)
}

def ssh(bash_commands, env_vars=[:])
{
    env_str= ""
    for (el in env_vars)
    {
        env_str+= "export ${el.key}=\"${el.value}\";"
    }
    sh "sudo ssh root@${TARGET_NODE_ADDRESS} '${env_str}${bash_commands}'"
}


def sftp_put(local_file,remote_dir)
{
    sh "echo 'put ${local_file}' | sudo sftp root@${TARGET_NODE_ADDRESS}:${remote_dir}"
}

def sftp_get(remote_path,local_filename)
{
    sh "echo 'get ${local_filename}' | sudo sftp root@${TARGET_NODE_ADDRESS}:${remote_path}"
}

node
{
echo "Begin deployment of ${APP_NAME} to ${TARGET_NODE_ADDRESS} with environment type ${ENVIRONMENT_TYPE}"

stage 'Checkout'
echo '===== Git Checkout ====='
checkout([
    $class: 'GitSCM', 
    branches: [[name: '*/master']], 
    doGenerateSubmoduleConfigurations: false, 
    extensions: [], 
    submoduleCfg: [], 
    userRemoteConfigs: [[url: 'https://github.com/MattSegal/Intesume.git']]
])

stage('Deploy')
{
    echo '===== Deployment ====='

    // Compress the payload
    sh "if [ -f ${ZIP_FILE} ];then rm ${ZIP_FILE};fi"
    sh "tar -zcf ${ZIP_FILE} ./*"

    sshagent(['jenkins']) 
    {
        // Print box name as debug step
        ssh('uname -a')

        // Kill gunicorn
        ssh("${VIRTUALENV_DIR}/bin/gunicorn_stop", [NAME: APP_NAME])

        // STFP and extract zip file
        ssh ("""
        if [ -f ${DEPLOY_DIR}/db.sqlite3 ];
        then mv ${DEPLOY_DIR}/db.sqlite3 /tmp/db.sqlite3;
        fi
        """)
        ssh("rm -rf ${DEPLOY_DIR}/*")
        sftp_put("./${ZIP_FILE}", "/tmp/")
        ssh("tar -zxf /tmp/${ZIP_FILE} --directory ${DEPLOY_DIR}/")
        ssh("rm /tmp/${ZIP_FILE}")
        ssh ("""
        if [ -f /tmp/db.sqlite3 ];
        then mv /tmp/db.sqlite3 ${DEPLOY_DIR}/db.sqlite3;
        fi
        """)
        ssh("chown www-data: ${DEPLOY_DIR}")

        // Add helper script to set required env vars
        ssh("""
        |touch ${VIRTUALENV_DIR}/bin/set_env_vars
        |
        |cat > ${VIRTUALENV_DIR}/bin/set_env_vars << EOM
        |export DEPLOY_STATUS='${ENVIRONMENT_TYPE}'
        |export DJANGO_STATIC_ROOT='/var/static'
        |export ALLOWED_HOSTS='${TARGET_NODE_ADDRESS}'
        |EOM
        |
        |chmod +x ${VIRTUALENV_DIR}/bin/set_env_vars
        """.stripMargin())
        
        // Start gunicorn + Django
        ssh("${VIRTUALENV_DIR}/bin/gunicorn_start deploy", [
            ALLOWED_HOSTS: "${TARGET_NODE_ADDRESS},${DOMAIN_NAME},www.${DOMAIN_NAME}",
            APP_NAME: APP_NAME,
            DJANGODIR: DEPLOY_DIR,
            LOGFILE: "${VIRTUALENV_DIR}/gunicorn.log",
            DJANGO_STATIC_ROOT: '/var/static',
            DEPLOY_STATUS: ENVIRONMENT_TYPE
        ])
    } // sshagent
} // stage

stage('Cleanup')
{
    echo 'Cleaning up job workspace'
    sh 'rm -rf ./*'
} // stage
} // node
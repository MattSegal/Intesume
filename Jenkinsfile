#!/usr/bin/env groovy

def jenkinsEnvVars = Jenkins.instance.getGlobalNodeProperties()[0].getEnvVars() 

env.ENVIRONMENT_TYPE = jenkinsEnvVars.ENVIRONMENT_TYPE ?: 'TEST' // TEST or PROD
env.TARGET_NODE_ADDRESS = jenkinsEnvVars.TARGET_NODE_ADDRESS ?: '45.55.161.12'
env.APP_NAME = 'links'

def unwanted_files = [
    'Jenkinsfile',
    'package.json',
    'README.md',
    'webpack.config.js',
]

def unwanted_folders = [
    'assets-src',
]

def WEBAPPS_DIR = '/var/webapps'
def DEPLOY_DIR = "${WEBAPPS_DIR}/${APP_NAME}/app"
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
    branches: [[name: '*/dev']], 
    doGenerateSubmoduleConfigurations: false, 
    extensions: [], 
    submoduleCfg: [], 
    userRemoteConfigs: [[url: 'https://github.com/MattSegal/Link-Sharing-Site.git']]
])


stage('Build')
{
    echo '===== Building ====='

    // Get cached node_modules
    sh ("""
    if [ -d /var/build/node_modules ]
    then 
        cp -r /var/build/node_modules ./node_modules
        npm rebuild node-sass
    else 
        mkdir -p /var/build/node_modules
    fi
    """)
    sh 'npm install'

    // Build javascript 
    sh "export ENVIRONMENT_TYPE='${ENVIRONMENT_TYPE}';webpack --config ./webpack.config.js"

    // Fix webpack-stats.json
    def process_webpack_stats = """
    |import json
    |file_path = \"./webpack-stats.json\"
    |with open(file_path,\"r\") as f:
    |    stats = json.load(f)
    |
    |if stats[\"status\"] != \"done\":
    |    raise Exception(stats)
    |
    |for idx in range(len(stats[\"chunks\"][\"main\"])):
    |    file_name = stats[\"chunks\"][\"main\"][idx][\"path\"].split(\"/\")[-1]
    |    stats[\"chunks\"][\"main\"][idx][\"path\"] = \"${DEPLOY_DIR}/assets/\" + file_name
    |
    |with open(file_path,\"w\") as f:
    |    json.dump(stats,f)
    """.stripMargin()
    sh "echo '${process_webpack_stats}' | python"

    // Cache node_modules
    sh 'rm -rf /var/build/node_modules'
    sh 'mv ./node_modules /var/build/node_modules'

    // Delete stuff we don't want/need
    for (folder in unwanted_folders)
    {
        sh "rm -rf ./${folder}"
    }

    for (file in unwanted_files)
    {
        sh "rm ./${file}"
    }
} // stage

stage('Deploy')
{
    echo '===== Deployment ====='

    // Compress the payload
    sh "if [ -f ${ZIP_FILE} ];then rm ${ZIP_FILE};fi"
    sh "tar -zcf ${ZIP_FILE} ./*"

    // Apply configuration with SaltStack
    echo 'Pulling latest SaltStack config'
    sh 'mkdir -p /srv'
    clone_or_pull('/srv/salt', 'https://github.com/MattSegal/WebserverSalt.git')

    echo 'Testing SaltStack connections'
    sh 'sudo salt "*" test.ping'

    echo 'Applying latest SaltStack config'
    sh 'sudo salt "*" state.highstate  -l debug'

    sshagent(['jenkins']) 
    {
        // Print box name as debug step
        ssh('uname -a')

        // Kill gunicorn
        ssh("${VIRTUALENV_DIR}/bin/gunicorn_stop", [NAME: APP_NAME])

        // STFP and extract zip file
        ssh("rm -rf ${DEPLOY_DIR}/*")
        sftp_put("./${ZIP_FILE}", "/tmp/")
        ssh("tar -zxf /tmp/${ZIP_FILE} --directory ${DEPLOY_DIR}/")
        ssh("rm /tmp/${ZIP_FILE}")
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

        // Update data from prod
        if (env.ENVIRONMENT_TYPE == 'TEST')
        {
           ssh("""
            source ${VIRTUALENV_DIR}/bin/activate
            source ${VIRTUALENV_DIR}/bin/set_env_vars
            python ${VIRTUALENV_DIR}/app/manage.py shell -c \"from api.factories import build;build()\"
            """)
        }

        // Create local database backups
        // restore with
        // > echo "DROP SCHEMA public CASCADE;CREATE SCHEMA public;" | sudo -u postgres -i psql $APP_NAME
        // > cat $BACKUP.gz | gunzip | sudo -u postgres -i psql $APP_NAME

        def backup_dir = "/var/backups/${APP_NAME}"
        def backup_file = "postgres_${BUILD_ID}.gz"
        def backup_path = "${backup_dir}/${backup_file}"
        ssh("""
        mkdir -p ${backup_dir}
        sudo -u postgres -i pg_dump ${APP_NAME} | gzip > ${backup_path}
        """)

        sftp_get(backup_path,backup_file)
        sh("""
        mkdir -p ${backup_dir}
        mv ${backup_file} ${backup_path}
        """)
        
        // Start gunicorn + Django
        ssh("${VIRTUALENV_DIR}/bin/gunicorn_start deploy", [
            ALLOWED_HOSTS: TARGET_NODE_ADDRESS,
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
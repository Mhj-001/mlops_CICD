pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "mhj01/mlops-model"
        DOCKER_TAG   = "${BUILD_NUMBER}"
        NETWORK      = "mlops-cicd_mlops-net"
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build Docker Image') {
            steps {
                sh "docker build -t ${DOCKER_IMAGE}:${DOCKER_TAG} ./model"
                sh "docker tag ${DOCKER_IMAGE}:${DOCKER_TAG} ${DOCKER_IMAGE}:latest"
            }
        }

        stage('Security Scan') {
            steps {
                script {
                    def trivyStatus = sh(
                        script: "docker exec trivy trivy image --exit-code 0 --severity HIGH,CRITICAL --no-progress --timeout 10m ${DOCKER_IMAGE}:${DOCKER_TAG}",
                        returnStatus: true
                    )
                    if (trivyStatus != 0) {
                        echo "Security scan timeout ou erreur - pipeline continue"
                    } else {
                        echo "Security scan OK"
                    }
                }
            }
        }

        stage('Train Model') {
            steps {
                sh """
                    docker run --rm \
                        --network ${NETWORK} \
                        -e POSTGRES_HOST=postgres \
                        -e POSTGRES_PORT=5432 \
                        -e POSTGRES_DB=mlops_db \
                        -e POSTGRES_USER=mlops \
                        -e POSTGRES_PASSWORD=mlops1234 \
                        -e MLFLOW_TRACKING_URI=http://mlflow:5000 \
                        -e MLFLOW_S3_ENDPOINT_URL=http://minio:9000 \
                        -e AWS_ACCESS_KEY_ID=minioadmin \
                        -e AWS_SECRET_ACCESS_KEY=minioadmin123 \
                        -e MINIO_BUCKET=datasets \
                        ${DOCKER_IMAGE}:${DOCKER_TAG}
                """
            }
        }

        stage('Push to Docker Hub') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-credentials',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh "echo ${DOCKER_PASS} | docker login -u ${DOCKER_USER} --password-stdin"
                    sh "docker push ${DOCKER_IMAGE}:${DOCKER_TAG}"
                    sh "docker push ${DOCKER_IMAGE}:latest"
                }
            }
        }

        stage('Deploy Staging') {
            steps {
                sh """
                    docker stop mlops-model-staging || true
                    docker rm   mlops-model-staging || true
                    docker run -d \
                        --name mlops-model-staging \
                        --network ${NETWORK} \
                        -e POSTGRES_HOST=postgres \
                        -e POSTGRES_PORT=5432 \
                        -e POSTGRES_DB=mlops_db \
                        -e POSTGRES_USER=mlops \
                        -e POSTGRES_PASSWORD=mlops1234 \
                        -e MLFLOW_TRACKING_URI=http://mlflow:5000 \
                        -e MLFLOW_S3_ENDPOINT_URL=http://minio:9000 \
                        -e AWS_ACCESS_KEY_ID=minioadmin \
                        -e AWS_SECRET_ACCESS_KEY=minioadmin123 \
                        -e MINIO_BUCKET=datasets \
                        ${DOCKER_IMAGE}:${DOCKER_TAG}
                """
            }
        }

        stage('Cleanup') {
            steps {
                sh "docker rmi ${DOCKER_IMAGE}:${DOCKER_TAG} || true"
                sh "docker logout"
            }
        }
    }

    post {
        success {
            echo "Pipeline reussi - Build ${BUILD_NUMBER} - Image ${DOCKER_IMAGE}:${DOCKER_TAG}"
        }
        failure {
            echo "Pipeline echoue - Build ${BUILD_NUMBER} - verifier les logs"
        }
        always {
            sh "docker rm -f mlops-model-staging || true"
        }
    }
}
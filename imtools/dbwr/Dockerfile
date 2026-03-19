FROM m.daocloud.io/docker.io/alpine/git:latest AS source_fetch

RUN git clone https://github.com/ornl-epics/dbwr.git /dbwr
ARG GIT_TAG=main
RUN cd /dbwr && git checkout ${GIT_TAG}
RUN git clone https://github.com/ornl-epics/pvws.git /pvws
ARG GIT_TAG=R4
RUN cd /pvws && git checkout ${GIT_TAG}

FROM m.daocloud.io/docker.io/maven:3.8.7-eclipse-temurin-17 AS maven_builder

COPY --from=source_fetch /dbwr /dbwr
RUN cd /dbwr && mvn clean package
COPY --from=source_fetch /pvws /pvws
RUN cd /pvws && mvn clean package

FROM m.daocloud.io/docker.io/tomcat:9.0-jdk17

ARG PORT_NUMBER=8088
COPY --from=maven_builder /dbwr/target/dbwr.war ${CATALINA_HOME}/webapps
COPY --from=maven_builder /pvws/target/pvws.war ${CATALINA_HOME}/webapps
RUN sed -i.bak -e "s|Connector port=\"8080\"|Connector port=\"${PORT_NUMBER}\"|g" \
  -e 's|Server port="8005" shutdown="SHUTDOWN"|Server port="-1" shutdown="SHUTDOWN"|g' \
   ${CATALINA_HOME}/conf/server.xml

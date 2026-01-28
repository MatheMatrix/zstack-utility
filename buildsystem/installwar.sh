#!/bin/sh

rm -rf $CATALINA_HOME/webapps/zstack*
rm -rf $CATALINA_HOME/webapps/cloud*
cp build/zstack.war $CATALINA_HOME/webapps/cloud.war

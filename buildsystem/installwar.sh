#!/bin/sh

# APP name variable - used to customize webapp path and war file name
# This is the only line that needs to be changed for APP builds
app_name="zstack"

rm -rf $CATALINA_HOME/webapps/${app_name}*
cp build/${app_name}.war $CATALINA_HOME/webapps/

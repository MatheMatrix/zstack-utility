#!/bin/sh

# OEM name variable - used to customize webapp path and war file name
# This is the only line that needs to be changed for OEM builds
oemname="zstack"

rm -rf $CATALINA_HOME/webapps/${oemname}*
cp build/${oemname}.war $CATALINA_HOME/webapps/

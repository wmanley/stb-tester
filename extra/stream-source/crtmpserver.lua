configuration=
{
  daemon=false,
  pathSeparator="/",
  logAppenders=
  {
    {
      name="file appender",
      type="file",
      level=6,
      fileName="/tmp/crtmpserver.log",
    }
  },
  applications=
  {
    rootDirectory="/usr/lib/crtmpserver/applications",
    {
      description="FLV Playback",
      name="flvplayback",
      protocol="dynamiclinklibrary",
      default=true,
      aliases=
      {
        "vod",
        "live",
      },
      acceptors =
      {
        {
          ip="0.0.0.0",
          port=1935,
          protocol="inboundRtmp"
        },
        {
            ip="0.0.0.0",
            port=5004,
            protocol="inboundUdpTs"
        },
        {
            ip="0.0.0.0",
            port=4953,
            protocol="inboundTcpTs"
        },
      },
      validateHandshake=false,
    },
  }
}

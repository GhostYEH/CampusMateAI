import { forwardRef, useEffect, useId, useRef, useState } from "react";
import "./GlassSurface.css";

const GlassSurface = forwardRef(function GlassSurface({
  children,
  borderRadius = 20,
  borderWidth = 0.07,
  brightness = 50,
  opacity = 0.93,
  blur = 11,
  displace = 0,
  backgroundOpacity = 0,
  saturation = 1,
  distortionScale = -180,
  redOffset = 0,
  greenOffset = 10,
  blueOffset = 20,
  xChannel = "R",
  yChannel = "G",
  mixBlendMode = "difference",
  className = "",
  style = {},
}, ref) {
  const uniqueId = useId().replace(/:/g, "-");
  const filterId = `glass-filter-${uniqueId}`;
  const redGradId = `red-grad-${uniqueId}`;
  const blueGradId = `blue-grad-${uniqueId}`;
  const [svgSupported, setSvgSupported] = useState(false);
  const containerRef = useRef(null);
  const feImageRef = useRef(null);
  const redChannelRef = useRef(null);
  const greenChannelRef = useRef(null);
  const blueChannelRef = useRef(null);
  const gaussianBlurRef = useRef(null);

  const setRefs = (node) => {
    containerRef.current = node;
    if (typeof ref === "function") ref(node);
    else if (ref) ref.current = node;
  };

  const generateDisplacementMap = () => {
    const rect = containerRef.current?.getBoundingClientRect();
    const actualWidth = rect?.width || 400;
    const actualHeight = rect?.height || 80;
    const edgeSize = Math.min(actualWidth, actualHeight) * (borderWidth * 0.5);
    const innerWidth = Math.max(0, actualWidth - edgeSize * 2);
    const innerHeight = Math.max(0, actualHeight - edgeSize * 2);
    const svgContent = `
      <svg viewBox="0 0 ${actualWidth} ${actualHeight}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="${redGradId}" x1="100%" y1="0%" x2="0%" y2="0%">
            <stop offset="0%" stop-color="#0000" />
            <stop offset="100%" stop-color="#6ea4ff" />
          </linearGradient>
          <linearGradient id="${blueGradId}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="#0000" />
            <stop offset="100%" stop-color="#b28cff" />
          </linearGradient>
        </defs>
        <rect width="${actualWidth}" height="${actualHeight}" fill="black" />
        <rect width="${actualWidth}" height="${actualHeight}" rx="${borderRadius}" fill="url(#${redGradId})" />
        <rect width="${actualWidth}" height="${actualHeight}" rx="${borderRadius}" fill="url(#${blueGradId})" style="mix-blend-mode: ${mixBlendMode}" />
        <rect x="${edgeSize}" y="${edgeSize}" width="${innerWidth}" height="${innerHeight}" rx="${Math.max(0, borderRadius - edgeSize)}" fill="hsl(0 0% ${brightness}% / ${opacity})" style="filter: blur(${blur}px)" />
      </svg>
    `;
    return `data:image/svg+xml,${encodeURIComponent(svgContent)}`;
  };

  const updateDisplacementMap = () => {
    feImageRef.current?.setAttribute("href", generateDisplacementMap());
  };

  useEffect(() => {
    updateDisplacementMap();
    [
      { ref: redChannelRef, offset: redOffset },
      { ref: greenChannelRef, offset: greenOffset },
      { ref: blueChannelRef, offset: blueOffset },
    ].forEach(({ ref: channelRef, offset }) => {
      channelRef.current?.setAttribute("scale", String(distortionScale + offset));
      channelRef.current?.setAttribute("xChannelSelector", xChannel);
      channelRef.current?.setAttribute("yChannelSelector", yChannel);
    });
    gaussianBlurRef.current?.setAttribute("stdDeviation", String(displace));
  }, [
    borderRadius,
    borderWidth,
    brightness,
    opacity,
    blur,
    displace,
    distortionScale,
    redOffset,
    greenOffset,
    blueOffset,
    xChannel,
    yChannel,
    mixBlendMode,
  ]);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const resizeObserver = new ResizeObserver(() => setTimeout(updateDisplacementMap, 0));
    resizeObserver.observe(containerRef.current);
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    const isUnsupportedBrowser = /Safari/.test(navigator.userAgent) && !/Chrome/.test(navigator.userAgent)
      || /Firefox/.test(navigator.userAgent);
    if (isUnsupportedBrowser) return;
    const probe = document.createElement("div");
    probe.style.backdropFilter = `url(#${filterId})`;
    setSvgSupported(probe.style.backdropFilter !== "");
  }, [filterId]);

  const containerStyle = {
    ...style,
    borderRadius: `${borderRadius}px`,
    "--glass-frost": backgroundOpacity,
    "--glass-saturation": saturation,
    "--filter-id": `url(#${filterId})`,
  };

  return (
    <div
      ref={setRefs}
      className={`glass-surface ${svgSupported ? "glass-surface--svg" : "glass-surface--fallback"} ${className}`}
      style={containerStyle}
    >
      <svg className="glass-surface__filter" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id={filterId} colorInterpolationFilters="sRGB" x="0%" y="0%" width="100%" height="100%">
            <feImage ref={feImageRef} x="0" y="0" width="100%" height="100%" preserveAspectRatio="none" result="map" />
            <feDisplacementMap ref={redChannelRef} in="SourceGraphic" in2="map" result="dispRed" />
            <feColorMatrix in="dispRed" type="matrix" values="1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0" result="red" />
            <feDisplacementMap ref={greenChannelRef} in="SourceGraphic" in2="map" result="dispGreen" />
            <feColorMatrix in="dispGreen" type="matrix" values="0 0 0 0 0 0 1 0 0 0 0 0 0 0 0 0 0 0 1 0" result="green" />
            <feDisplacementMap ref={blueChannelRef} in="SourceGraphic" in2="map" result="dispBlue" />
            <feColorMatrix in="dispBlue" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 0 0 1 0" result="blue" />
            <feBlend in="red" in2="green" mode="screen" result="rg" />
            <feBlend in="rg" in2="blue" mode="screen" result="output" />
            <feGaussianBlur ref={gaussianBlurRef} in="output" stdDeviation="0" />
          </filter>
        </defs>
      </svg>
      <div className="glass-surface__content">{children}</div>
    </div>
  );
});

export default GlassSurface;

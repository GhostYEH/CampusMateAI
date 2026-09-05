import { useRef } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import "./TiltedCard.css";

const springValues = { damping: 30, stiffness: 100, mass: 2 };

export default function TiltedCard({
  children = null,
  imageSrc = "",
  altText = "Tilted card image",
  captionText = "",
  containerHeight = "300px",
  containerWidth = "100%",
  imageHeight = "300px",
  imageWidth = "300px",
  scaleOnHover = 1.1,
  rotateAmplitude = 14,
  showMobileWarning = true,
  showTooltip = true,
  className = "",
}) {
  const ref = useRef(null);
  const lastY = useRef(0);
  const reducedMotion = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const rotateX = useSpring(useMotionValue(0), springValues);
  const rotateY = useSpring(useMotionValue(0), springValues);
  const scale = useSpring(1, springValues);
  const opacity = useSpring(0, springValues);
  const rotateFigcaption = useSpring(0, { stiffness: 350, damping: 30, mass: 1 });

  function handleMouse(event) {
    if (!ref.current || reducedMotion) return;
    const rect = ref.current.getBoundingClientRect();
    const offsetX = event.clientX - rect.left - rect.width / 2;
    const offsetY = event.clientY - rect.top - rect.height / 2;
    rotateX.set((offsetY / (rect.height / 2)) * -rotateAmplitude);
    rotateY.set((offsetX / (rect.width / 2)) * rotateAmplitude);
    x.set(event.clientX - rect.left);
    y.set(event.clientY - rect.top);
    rotateFigcaption.set(-(offsetY - lastY.current) * 0.6);
    lastY.current = offsetY;
  }

  function handleMouseEnter() {
    scale.set(reducedMotion ? 1 : scaleOnHover);
    opacity.set(1);
  }

  function handleMouseLeave() {
    opacity.set(0);
    scale.set(1);
    rotateX.set(0);
    rotateY.set(0);
    rotateFigcaption.set(0);
    lastY.current = 0;
  }

  return (
    <figure
      ref={ref}
      className={["tilted-card-figure", className].filter(Boolean).join(" ")}
      style={{ height: containerHeight, width: containerWidth }}
      onMouseMove={handleMouse}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {showMobileWarning && <div className="tilted-card-mobile-alert">此卡片动效更适合桌面端浏览</div>}
      <motion.div
        className="tilted-card-inner"
        style={{ width: children ? "100%" : imageWidth, height: children ? "auto" : imageHeight, rotateX, rotateY, scale }}
      >
        {children || <motion.img src={imageSrc} alt={altText} className="tilted-card-img" style={{ width: imageWidth, height: imageHeight }} />}
      </motion.div>
      {showTooltip && captionText && <motion.figcaption className="tilted-card-caption" style={{ x, y, opacity, rotate: rotateFigcaption }}>{captionText}</motion.figcaption>}
    </figure>
  );
}

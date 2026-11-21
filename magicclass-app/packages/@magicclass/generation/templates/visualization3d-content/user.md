Create a 3D visualization widget for: {{title}}

## Visualization Type

{{visualizationType}}

## Description

{{description}}

## Key Points

{{keyPoints}}

## Objects to Visualize

{{objects}}

## Interactions

{{interactions}}

## Language

{{languageDirective}}

---

Generate a complete, interactive 3D visualization using Three.js with these MANDATORY features:

### Scene Setup
1. **Three.js from CDN** using importmap for ES modules
2. **Proper lighting** (ambient + directional/point lights)
3. **OrbitControls** for camera manipulation
4. **Responsive canvas** that fills the container

### Objects
1. Create 3D objects based on the visualization type
2. Use appropriate materials (Phong, Standard, Emissive)
3. Add meaningful colors and textures
4. Store objects in an `objects` dictionary for widget actions

### Interactions
1. For the portable profile provide orbit, zoom, reset and the shared animation toggle when animated.
2. For web-specific exercises provide the sliders and presets needed by the learning objective.
3. Use a readable info panel and touch-friendly controls (44px minimum).

### Animation
1. Use `requestAnimationFrame` for smooth animations
2. Support pause/play controls
3. Respect `animationSpeed` variable

### Teacher Actions Support
1. Include the postMessage listener
2. Support SET_WIDGET_STATE for camera and object control
3. Support HIGHLIGHT_ELEMENT for 3D objects
4. Support ANNOTATE_ELEMENT for 3D objects

### Widget Config
Embed complete JSON in `<script type="application/json" id="widget-config">`. Use the `classroom-spatial/1` profile from the system instructions when the actual experiment fits it. Include the objects, transforms, materials and motion actually shown in the lesson. Use the browser profile when a web-specific feature is essential.

### Mobile Considerations
1. Touch-enabled OrbitControls
2. Lower polygon count for mobile
3. Control panel at bottom for thumb access
4. Readable text sizes

Return ONLY the HTML document.

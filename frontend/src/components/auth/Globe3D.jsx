import { useEffect, useRef } from "react";
import * as THREE from "three";

// Photo-real, slowly-rotating Earth: NASA Blue Marble day map, topology bump,
// ocean specular, night-side city lights, drifting clouds and a Fresnel
// atmosphere rim — with filmic tone mapping. Purely decorative:
// pointer-events-none, honors prefers-reduced-motion, disposes WebGL on unmount.
export default function Globe3D({ className = "" }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    let width = mount.clientWidth || 1;
    let height = mount.clientHeight || 1;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    camera.position.z = 5.2;

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    mount.appendChild(renderer.domElement);

    // ---- Lighting: cool ambient fill + a strong "sun" for a real terminator ----
    scene.add(new THREE.AmbientLight(0x6b7a99, 0.55));
    const sun = new THREE.DirectionalLight(0xfff4e6, 2.3);
    sun.position.set(-1.4, 0.7, 1.2);
    scene.add(sun);

    const group = new THREE.Group();
    group.rotation.z = 0.41; // ~23.5° axial tilt
    scene.add(group);

    const RADIUS = 1.85;
    const loader = new THREE.TextureLoader();
    const maxAniso = renderer.capabilities.getMaxAnisotropy();
    const load = (url, srgb = false) => {
      const t = loader.load(url, () => renderer.render(scene, camera));
      if (srgb) t.colorSpace = THREE.SRGBColorSpace;
      t.anisotropy = maxAniso;
      return t;
    };

    const TEX = import.meta.env.BASE_URL; // respects the deploy base (e.g. "/jobora/")
    const dayMap = load(`${TEX}textures/earth.jpg`, true);
    const nightMap = load(`${TEX}textures/night.jpg`, true);
    const bump = load(`${TEX}textures/bump.png`);
    const spec = load(`${TEX}textures/spec.jpg`);

    // ---- Earth ----
    const earth = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS, 96, 96),
      new THREE.MeshPhongMaterial({
        map: dayMap,
        bumpMap: bump,
        bumpScale: 0.05,
        specularMap: spec,
        specular: new THREE.Color(0x4a6080),
        shininess: 18,
        emissiveMap: nightMap,
        emissive: new THREE.Color(0xffffff),
        emissiveIntensity: 0.9, // night-side city lights
      })
    );
    group.add(earth);

    // ---- Clouds ----
    const cloudsTex = load(`${TEX}textures/clouds.png`);
    const clouds = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS * 1.012, 64, 64),
      new THREE.MeshLambertMaterial({
        map: cloudsTex,
        alphaMap: cloudsTex,
        transparent: true,
        opacity: 0.5,
        depthWrite: false,
      })
    );
    group.add(clouds);

    // ---- Fresnel atmosphere rim ----
    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(RADIUS * 1.18, 64, 64),
      new THREE.ShaderMaterial({
        transparent: true,
        side: THREE.BackSide,
        depthWrite: false,
        uniforms: {
          glowColor: { value: new THREE.Color(0x5b9dff) },
          power: { value: 2.8 },
          strength: { value: 0.9 },
        },
        vertexShader: `
          varying vec3 vNormal; varying vec3 vView;
          void main() {
            vNormal = normalize(normalMatrix * normal);
            vec4 mv = modelViewMatrix * vec4(position, 1.0);
            vView = -mv.xyz;
            gl_Position = projectionMatrix * mv;
          }`,
        fragmentShader: `
          varying vec3 vNormal; varying vec3 vView;
          uniform vec3 glowColor; uniform float power; uniform float strength;
          void main() {
            float rim = pow(1.0 - abs(dot(normalize(vView), normalize(vNormal))), power);
            gl_FragColor = vec4(glowColor, rim * strength);
          }`,
      })
    );
    group.add(atmosphere);

    let raf;
    const animate = () => {
      if (!reduce) {
        earth.rotation.y += 0.0011;
        clouds.rotation.y += 0.0014;
      }
      renderer.render(scene, camera);
      if (!reduce) raf = requestAnimationFrame(animate);
    };
    animate();
    if (reduce) renderer.render(scene, camera);

    const onResize = () => {
      width = mount.clientWidth || 1;
      height = mount.clientHeight || 1;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      [earth, clouds, atmosphere].forEach((m) => {
        m.geometry.dispose();
        m.material.dispose();
      });
      [dayMap, nightMap, bump, spec, cloudsTex].forEach((t) => t.dispose());
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} className={`pointer-events-none ${className}`} aria-hidden />;
}

"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

type Props = {
  stlUrl: string | null;
};

export default function ThreeViewer({ stlUrl }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !stlUrl) return;

    const width = mount.clientWidth;
    const height = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x111318);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000);
    camera.position.set(120, 120, 120);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.9);
    dir.position.set(1, 1, 1);
    scene.add(dir);
    scene.add(new THREE.GridHelper(300, 30, 0x333333, 0x222222));

    let mesh: THREE.Mesh | null = null;
    const loader = new STLLoader();
    loader.load(stlUrl, (geometry) => {
      geometry.center();
      geometry.computeVertexNormals();
      const material = new THREE.MeshStandardMaterial({
        color: 0x4f9dff,
        metalness: 0.1,
        roughness: 0.6,
      });
      mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      // Recadre la caméra sur la bounding box.
      geometry.computeBoundingSphere();
      const r = geometry.boundingSphere?.radius ?? 100;
      camera.position.set(r * 2, r * 2, r * 2);
      controls.update();
    });

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (mesh) {
        mesh.geometry.dispose();
        (mesh.material as THREE.Material).dispose();
      }
      mount.removeChild(renderer.domElement);
    };
  }, [stlUrl]);

  return (
    <div
      ref={mountRef}
      style={{
        width: "100%",
        height: "420px",
        borderRadius: "12px",
        overflow: "hidden",
        border: "1px solid #2a2d35",
      }}
    >
      {!stlUrl && (
        <div style={{ padding: "1rem", color: "#888" }}>
          Le modèle 3D apparaîtra ici.
        </div>
      )}
    </div>
  );
}

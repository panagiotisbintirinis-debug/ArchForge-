// Entry for the offline three.js bundle used by the 3D Scene.
// Rebuild (three 0.169.0, esbuild 0.24):
//   npm i three@0.169.0 esbuild@0.24
//   npx esbuild scripts/three_bundle_entry.js --bundle --minify --format=iife \
//       --outfile=archforge/ui/vendor/three_bundle.js
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { GTAOPass } from 'three/addons/postprocessing/GTAOPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Sky } from 'three/addons/objects/Sky.js';

window.__ARCHFORGE_THREE = {
  THREE, OrbitControls, RoomEnvironment, EffectComposer, RenderPass, GTAOPass, OutputPass, Sky,
};

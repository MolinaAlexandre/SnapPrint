// ==========================================
// LIB_PRIMITIVES.SCAD - SnapPrint / SnapCAD Kernel
// Bibliothèque de briques paramétriques (CSG).
// L'agent assemble ces modules, il ne manipule jamais de polygones bruts.
// ==========================================
$fn = 60;

// 1. EMPREINTE NÉGATIVE ADAPTATIVE
//    Prend le polygone 2D (issu de SAM) et l'extrude en cavité à évider.
module negative_cavity(points_2d, depth, tolerance = 0.5) {
    linear_extrude(height = depth)
        offset(r = tolerance)
            polygon(points = points_2d);
}

// 2. SOCLE INCLINÉ (souris, télécommandes, téléphones)
module angled_dock_body(width, depth, height, angle = 20) {
    rotate([angle, 0, 0])
    difference() {
        // Base arrondie.
        minkowski() {
            cube([width, depth, height], center = true);
            cylinder(r = 3, h = 1);
        }
        // Évidement inférieur (stabilité sur bureau).
        translate([0, 0, -height / 2 - 1])
            cube([width - 10, depth - 10, 5], center = true);
    }
}

// 3. PASSAGE DE CÂBLE (USB-C, Lightning)
module cable_channel(width = 6.0, height = 35.0, depth = 10.0) {
    cylinder(d = width, h = height, center = true);
    translate([0, depth / 2, 0])
        cube([width, depth, height], center = true);
}

// 4. CHÂSSIS F1 / SIM-RACING (plaque centrale)
module f1_chassis(width = 280, height = 150, thickness = 5) {
    linear_extrude(height = thickness)
    hull() {
        translate([-width / 2 + 20, 0]) circle(r = 20);
        translate([ width / 2 - 20, 0]) circle(r = 20);
        translate([-width / 3, -height / 2 + 20]) circle(r = 15);
        translate([ width / 3, -height / 2 + 20]) circle(r = 15);
        translate([0, height / 2 - 15]) circle(r = 25);
    }
}

// 5. POIGNÉE ERGONOMIQUE F1 (grip gauche/droite)
module f1_grip(length = 120, radius = 16, angle = 10) {
    rotate([0, angle, 0])
    hull() {
        sphere(r = radius);
        translate([0, 0, -length]) sphere(r = radius * 0.85);
    }
}

// 6. PERÇAGES STANDARD (boutons 12mm ou vis murales)
//    positions : liste de [x, y, diametre]
module button_cutouts(positions) {
    for (pos = positions) {
        translate([pos[0], pos[1], -10])
            cylinder(d = pos[2], h = 30);
    }
}

// 7. FIXATION MOYEU STANDARD SIM-RACING (70mm PCD, 6 trous M5)
module wheel_hub_mount_70mm() {
    pcd = 70.0;
    for (i = [0 : 5]) {
        rotate([0, 0, i * 60])
            translate([pcd / 2, 0, -10])
                cylinder(d = 5.2, h = 30); // Trous M5
    }
    // Trou d'axe central.
    cylinder(d = 20, h = 30, center = true);
}

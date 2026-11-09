CREATE VIEW v_atom_molecule AS SELECT atom.atom_id, atom.molecule_id, atom.element, molecule.label AS molecule_label, molecule.molecule_id AS molecule_molecule_id FROM atom LEFT JOIN molecule ON atom.molecule_id = molecule.molecule_id;

CREATE VIEW v_bond_molecule AS SELECT bond.bond_id, bond.molecule_id, bond.bond_type, molecule.label AS molecule_label, molecule.molecule_id AS molecule_molecule_id FROM bond LEFT JOIN molecule ON bond.molecule_id = molecule.molecule_id;

CREATE VIEW v_atom_bond AS SELECT atom.atom_id, atom.molecule_id, atom.element, bond.bond_id, bond.molecule_id AS bond_molecule_id, bond.bond_type FROM atom INNER JOIN bond ON atom.molecule_id = bond.molecule_id;

CREATE VIEW v_atom_bond_connected AS SELECT atom.atom_id, atom.molecule_id, atom.element, bond.bond_id, bond.molecule_id AS bond_molecule_id, bond.bond_type, connected.atom_id AS connected_atom_id, connected.atom_id2, connected.bond_id AS connected_bond_id FROM atom INNER JOIN bond ON atom.molecule_id = bond.molecule_id INNER JOIN connected ON atom.atom_id = connected.atom_id;

CREATE VIEW v_atom_bond_molecule AS SELECT atom.atom_id, atom.molecule_id, atom.element, bond.bond_id, bond.molecule_id AS bond_molecule_id, bond.bond_type, molecule.molecule_id AS molecule_molecule_id, molecule.label FROM atom INNER JOIN bond ON atom.molecule_id = bond.molecule_id INNER JOIN molecule ON atom.molecule_id = molecule.molecule_id;

CREATE VIEW v_atom_connected AS SELECT atom.atom_id, atom.molecule_id, atom.element, connected.atom_id AS connected_atom_id, connected.atom_id2, connected.bond_id FROM atom INNER JOIN connected ON atom.atom_id = connected.atom_id;

CREATE VIEW v_bond_connected AS SELECT bond.bond_id, bond.molecule_id, bond.bond_type, connected.atom_id, connected.atom_id2, connected.bond_id AS connected_bond_id FROM bond INNER JOIN connected ON bond.bond_id = connected.bond_id;

CREATE VIEW v_connected AS SELECT connected.atom_id, connected.atom_id2, connected.bond_id FROM connected;

CREATE VIEW v_atom_molecule AS SELECT atom.atom_id, atom.molecule_id, atom.element, molecule.label AS molecule_label, molecule.molecule_id AS molecule_molecule_id FROM atom LEFT JOIN molecule ON atom.molecule_id = molecule.molecule_id;

CREATE VIEW v_bond_molecule AS SELECT bond.bond_id, bond.molecule_id, bond.bond_type, molecule.label AS molecule_label, molecule.molecule_id AS molecule_molecule_id FROM bond LEFT JOIN molecule ON bond.molecule_id = molecule.molecule_id;

CREATE VIEW v_atom_bond_connected AS SELECT connected.atom_id, connected.atom_id2, connected.bond_id, atom.atom_id AS atom_atom_id, atom.molecule_id, atom.element, bond.bond_id AS bond_bond_id, bond.molecule_id AS bond_molecule_id, bond.bond_type FROM connected LEFT JOIN atom ON connected.atom_id = atom.atom_id LEFT JOIN bond ON atom.molecule_id = bond.molecule_id;

CREATE VIEW v_atom_bond_molecule AS SELECT bond.bond_id, bond.molecule_id, bond.bond_type, atom.atom_id, atom.molecule_id AS atom_molecule_id, atom.element, molecule.molecule_id AS molecule_molecule_id, molecule.label FROM bond LEFT JOIN atom ON bond.molecule_id = atom.molecule_id LEFT JOIN molecule ON atom.molecule_id = molecule.molecule_id;

CREATE VIEW v_atom_connected AS SELECT connected.atom_id, connected.atom_id2, connected.bond_id, atom.atom_id AS atom_atom_id, atom.molecule_id, atom.element FROM connected LEFT JOIN atom ON connected.atom_id = atom.atom_id;

CREATE VIEW v_bond_connected AS SELECT connected.atom_id, connected.atom_id2, connected.bond_id, bond.bond_id AS bond_bond_id, bond.molecule_id, bond.bond_type FROM connected LEFT JOIN bond ON connected.bond_id = bond.bond_id;

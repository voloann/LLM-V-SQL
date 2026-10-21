-- Views thu cong cho database toxicology (Paper V-SQL style)

-- 1. View ket hop atom va molecule
CREATE VIEW v_atom_molecule AS
SELECT
    atom.atom_id,
    atom.molecule_id,
    atom.element,
    molecule.label AS molecule_label
FROM atom
LEFT JOIN molecule ON atom.molecule_id = molecule.molecule_id;

-- 2. View ket hop bond va molecule
CREATE VIEW v_bond_molecule AS
SELECT
    bond.bond_id,
    bond.molecule_id,
    bond.bond_type,
    molecule.label AS molecule_label
FROM bond
LEFT JOIN molecule ON bond.molecule_id = molecule.molecule_id;

def migrate(cr, version):
    # Ajouter la colonne sale_order_id
    cr.execute("""
        ALTER TABLE booking 
        ADD COLUMN sale_order_id integer;

        -- Ajouter la contrainte de clé étrangère
        ALTER TABLE booking
        ADD CONSTRAINT booking_sale_order_fkey 
        FOREIGN KEY (sale_order_id) 
        REFERENCES sale_order(id) ON DELETE SET NULL;
    """)
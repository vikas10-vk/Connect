"""
Seed all 148 tradie service categories into the categories table.

Run from backend directory:
    python scripts/seed_categories.py

Idempotent: safe to run multiple times (skips existing slugs).
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid

from sqlalchemy import select

from db.session import AsyncSessionLocal
from models.category import Category

SERVICES = [
    "Air Conditioning Installer / Supplier",
    "Antenna Installer / Supplier",
    "Appliance Installer",
    "Appliance Repairer",
    "Arborist",
    "Architect",
    "Asbestos Removal Expert",
    "Awning Installer / Supplier",
    "Balustrading Installer",
    "Bamboo Flooring Installer / Supplier",
    "Bath and Basin Resurfacing",
    "Bathroom Building / Renovations",
    "Blinds Installer / Supplier",
    "Bricklayer",
    "Builder",
    "Building Certifier",
    "Building Consultant",
    "Building Designer",
    "Building Inspector",
    "Building Surveyor",
    "Cabinet Maker",
    "Carpenter",
    "Carpet / Upholstery Cleaning",
    "Carpet Layer / Repairs",
    "Carport Builder",
    "Chimney Sweeper",
    "Cladding Installer",
    "Commercial Cleaning Services",
    "Concrete Kerb Builder",
    "Concrete Resurfacer",
    "Concretor",
    "Construction Project Manager",
    "Curtain Installer / Supplier",
    "Custom Furniture Designer",
    "Damp Proofing Services",
    "Deck Builder",
    "Deep Cleaning",
    "Demolition Services",
    "Door Installer / Supplier",
    "Drafter",
    "Drains Installer / Maintenance",
    "Electrician",
    "Equipment Hire Supplier",
    "EV Charger Installation",
    "Excavation Services",
    "Fence Builder",
    "Fence Repairs",
    "Floor Coating",
    "Floor Sanding & Polishing Services",
    "Fly Screen Installer / Supplier",
    "Frame and Truss Maintenance / Supplier",
    "Garage Builder",
    "Garden Designer",
    "Gardener",
    "Gas Fitter",
    "Gate Installer / Supplier",
    "Gazebo Builder / Supplier",
    "Glazier",
    "Glass Balustrade Installer / Supplier",
    "Gutter Installer / Maintenance / Supplier",
    "Handyman",
    "Heating System Installer / Supplier",
    "Hot Water System Installer / Supplier",
    "Hybrid Flooring",
    "Insulation Installer / Supplier",
    "Interior Decorator",
    "Interior Designer",
    "Irrigation System Expert",
    "Joiner",
    "Kitchen Building / Renovations",
    "Kitchen Designer",
    "Landscape Architect",
    "Landscaper",
    "Lawn and Turf Installer / Supplier",
    "Lawn Mowing Services",
    "Leak Detection",
    "Lighting Expert",
    "Locksmith",
    "Mattress Cleaning",
    "Painter",
    "Patio Builder",
    "Paving",
    "Paving Supplier",
    "Pergola Builder",
    "Pest Control Services",
    "Pest Inspector",
    "Plasterer",
    "Plumber",
    "Pool Builder",
    "Pool Fence Installer / Maintenance",
    "Pool Maintenance Services",
    "Pressure Cleaning Services",
    "Rainwater Tanks Installer / Supplier",
    "Renderer",
    "Renovation and Extensions Builder",
    "Reproduction Stone Supplier",
    "Retaining Wall Builder",
    "Roller Door Installer / Supplier",
    "Roofer",
    "Rubbish Removal Services",
    "Scaffolding Services",
    "Screen Enclosure Supplier",
    "Security Screen Installer / Supplier",
    "Security Systems Specialist",
    "Shade and Sail Installer / Supplier",
    "Shed Builder / Supplier",
    "Shopfitter",
    "Shower Screen Installer / Supplier",
    "Skip and Truck Hire Services",
    "Skylight Installer / Supplier",
    "Soil Testing",
    "Solar Installer / Supplier",
    "Splashback Installer / Supplier",
    "Stonemason",
    "Storage Services",
    "Structural Engineer",
    "Surveyor",
    "Tile Supplier",
    "Tiler",
    "Timber Floor Installation / Repairs",
    "Town Planner",
    "Tree Feller",
    "Underfloor Heating Installer / Supplier",
    "Underpinning Services",
    "Upholstery Repairer",
    "Ventilation System Specialists",
    "Vinyl and Laminate Installer",
    "Wallpaper Installer / Supplier",
    "Wardrobe Builder",
    "Waterproofer",
    "Window Cleaning Services",
    "Window Installer / Repairs",
    "Window Shutter Installer / Supplier",
    "Window Tinting Services",
]


def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")


async def seed():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Category))
        existing_slugs = {c.slug for c in result.scalars().all()}

        added = 0
        for name in SERVICES:
            slug = slugify(name)
            if slug in existing_slugs:
                continue
            cat = Category(id=str(uuid.uuid4()), name=name, slug=slug)
            db.add(cat)
            existing_slugs.add(slug)
            added += 1

        await db.commit()
        print(f"[seed_categories] Done. Added {added} new categories ({len(SERVICES) - added} already existed).")


if __name__ == "__main__":
    asyncio.run(seed())

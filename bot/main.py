from typing import Optional
import numpy as np
import random
from loguru import logger

from sc2 import maps
from ares import AresBot
from sc2.data import Difficulty, Race, Result
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.position import Point2, Point3
from sc2.unit import Unit
from sc2.units import Units
from sc2 import pixel_map
from ares.behaviors.macro import Mining

# pylint: disable=W0231
class ZergRushBot:

    def __init__(self):
        self.defender = 0
        self.mineralMatch = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, -1, -1, -1, -1]
        self.currTarget = 0
        self.randoming = False
        self.attacking = False
        self.fighting = False
        self.makingZerglings = True
        self.target: Point2 = (0.0, 0.0)
        self.extractorMade = False
        self.wave_length: dict = {
            "c033a97a-667d-42e3-91e8-13528ac191ed" : 40
        }

    # pylint: disable=R0912
    async def on_step(self, bot, iteration):
        # Draw creep pixelmap for debugging
        # self.draw_creep_pixelmap()
        if iteration == 2:
            self.target = bot.enemy_start_locations[0].position

        #if iteration == 8000:
        #    bot.townhalls[0].upgrade(UP)

        # If townhall no longer exists: attack move with all units to enemy start location
        if not bot.townhalls:
            for unit in bot.units.exclude_type({UnitTypeId.EGG, UnitTypeId.LARVA}):
                unit.attack(bot.enemy_start_locations[0])
            return

        hatch: Unit = bot.townhalls[0]

        # Pick a target location

        minimumDist: int = 1000
        enemy_structure_count: int = 0
        for enemy_structure in bot.enemy_structures:
            enemy_structure_count = enemy_structure_count+1
        for zergling in bot.units(UnitTypeId.ZERGLING):
            minimumDist = min(minimumDist, zergling.distance_to(self.target))
        if minimumDist < 10:
            self.fighting = True
        else:
            self.fighting = False
        if enemy_structure_count == 0 and self.fighting:
            self.randoming = True
            self.fighting = False


        # Give all zerglings an attack command

        zerglings: int = 0
        for zergling in bot.units(UnitTypeId.ZERGLING):
            zerglings = zerglings+1
        
        if zerglings >= 100:
            self.makingZerglings = False
            if(bot.gas_buildings.ready):
                extractor: Unit = bot.gas_buildings.first
                if extractor.surplus_harvesters < 0:
                    bot.workers.random.gather(extractor)
            if bot.structures(UnitTypeId.LAIR).amount + bot.already_pending(UnitTypeId.LAIR) == 0 and bot.can_afford(UnitTypeId.LAIR) and hatch.is_idle:
                bot.do(hatch(AbilityId.UPGRADETOLAIR_LAIR))
            if bot.structures(UnitTypeId.LAIR).ready.exists and not bot.structures(UnitTypeId.SPIRE).exists and bot.can_afford(UnitTypeId.SPIRE) and bot.already_pending(UnitTypeId.SPIRE) == 0:
                for d in range(5, 15):
                    loc: Point2 = hatch.position.towards(bot.game_info.map_center, d).offset((3, 0))
                    if await bot.can_place_single(UnitTypeId.SPIRE, loc):
                        if worker := bot.mediator.select_worker(target_position=loc):
                            bot.mediator.build_with_specific_worker(
                            worker=worker, structure_type=UnitTypeId.SPIRE, pos=loc
                            )
                            break
            if bot.structures(UnitTypeId.SPIRE).ready.exists and bot.can_afford(UnitTypeId.MUTALISK):
                bot.train(UnitTypeId.MUTALISK)
        
            

        if bot.opponent_id in self.wave_length:
            if zerglings >= self.wave_length[bot.opponent_id]:
                self.attacking = True
        else:
            if zerglings >= 1:
                self.attacking = True

        if not self.randoming and self.attacking:
            if minimumDist < 1 and enemy_structure_count > 0:
                self.target = bot.enemy_structures[0].position
            for zergling in bot.units(UnitTypeId.ZERGLING):
                zergling.attack(self.target)
            for mutalisk in bot.units(UnitTypeId.MUTALISK):
                mutalisk.attack(self.target)
        elif self.randoming:
            for zergling in bot.units(UnitTypeId.ZERGLING):
                if not zergling.is_active:
                    rPos: Point2 = bot.expansion_locations_list[random.randrange(0, len(bot.expansion_locations_list)-1)]
                    zergling.attack(rPos)
            for mutalisk in bot.units(UnitTypeId.MUTALISK):
                if not mutalisk.is_active:
                    rPos: Point2 = (random.randrange(0, 255), random.randrange(0, 255))
                    mutalisk.attack(rPos)
            if enemy_structure_count > 0:
                self.target = bot.enemy_structures[0].position
                self.randoming = False
                self.fighting = True
            
        '''
        for roach in bot.units(UnitTypeId.ROACH):
            roach.attack(target)
            attacking = True
        '''
        # Inject hatchery if queen has more than 25 energy
        if self.makingZerglings:
            for queen in bot.units(UnitTypeId.QUEEN):
                if queen.energy >= 25 and not hatch.has_buff(BuffId.QUEENSPAWNLARVATIMER):
                    queen(AbilityId.EFFECT_INJECTLARVA, hatch)
        
        # Pull workers out of gas if we have almost enough gas mined, this will stop mining when we reached 100 gas mined
        if self.makingZerglings:
            if bot.vespene >= 88 or bot.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED) > 0:
                gas_drones: Units = bot.workers.filter(lambda w: w.is_carrying_vespene and len(w.orders) < 2)
                drone: Unit
                for drone in gas_drones:
                    minerals: Units = bot.mineral_field.closer_than(10, hatch)
                    if minerals:
                        mineral: Unit = minerals.closest_to(drone)
                        drone.gather(mineral, queue=True)
                        
        
        # If we have 100 vespene, this will try to research zergling speed once the spawning pool is at 100% completion
        if bot.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED
                                        ) == 0 and bot.can_afford(UpgradeId.ZERGLINGMOVEMENTSPEED):
            spawning_pools_ready: Units = bot.structures(UnitTypeId.SPAWNINGPOOL).ready
            if spawning_pools_ready:
                bot.research(UpgradeId.ZERGLINGMOVEMENTSPEED)

        # If we have less than 2 supply left and no overlord is in the queue: train an overlord
        if bot.supply_left < 2 and bot.already_pending(UnitTypeId.OVERLORD) < 1:
            bot.train(UnitTypeId.OVERLORD, 1)

        # While we have less than 88 vespene mined: send drones into extractor one frame at a time
        if (
            bot.gas_buildings.ready and bot.vespene < 88
            and bot.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED) == 0
        ):
            extractor: Unit = bot.gas_buildings.first
            if extractor.surplus_harvesters < 0:
                bot.workers.random.gather(extractor)

        # If we have lots of minerals, make a macro hatchery
        if bot.minerals > 500:
            for d in range(9, 15):
                loc: Point2 = hatch.position.towards(bot.game_info.map_center, d)
                if await bot.can_place_single(UnitTypeId.HATCHERY, loc):
                    if worker := bot.mediator.select_worker(target_position=loc):
                        bot.mediator.build_with_specific_worker(
                        worker=worker, structure_type=UnitTypeId.HATCHERY, pos=loc
                        )
                        break

        # While we have less than 16 drones, make more drones
        if bot.can_afford(UnitTypeId.DRONE) and bot.supply_workers+bot.already_pending(UnitTypeId.DRONE) < 16 and bot.structures(UnitTypeId.SPAWNINGPOOL).amount > 0:
            bot.train(UnitTypeId.DRONE)
        
        # If our spawningpool is completed, start making zerglings
        
        if self.makingZerglings and self.makingZerglings and bot.structures(UnitTypeId.SPAWNINGPOOL).ready and bot.larva and bot.can_afford(UnitTypeId.ZERGLING):
            _amount_trained: int = bot.train(UnitTypeId.ZERGLING, bot.larva.amount)

        # If we have no spawning pool, try to build spawning pool
        if bot.structures(UnitTypeId.SPAWNINGPOOL).amount + bot.already_pending(UnitTypeId.SPAWNINGPOOL) == 0:
            if bot.can_afford(UnitTypeId.SPAWNINGPOOL):
                for d in range(4, 15):
                    loc: Point2 = hatch.position.towards(bot.game_info.map_center, d)
                    if await bot.can_place_single(UnitTypeId.SPAWNINGPOOL, loc):
                        if worker := bot.mediator.select_worker(target_position=loc):
                            bot.mediator.build_with_specific_worker(
                            worker=worker, structure_type=UnitTypeId.SPAWNINGPOOL, pos=loc
                            )
                            break

        # If we have no extractor, build extractor
        elif (not self.extractorMade and bot.can_afford(UnitTypeId.EXTRACTOR) and bot.workers):
            loc: Point2 = bot.vespene_geyser.closest_to(hatch)
            if worker := bot.mediator.select_worker(target_position=loc):
                bot.mediator.build_with_specific_worker(
                worker=worker, structure_type=UnitTypeId.EXTRACTOR, pos=loc
            )   
            self.extractorMade = True


        # If we have no queen, try to build a queen if we have a spawning pool compelted
        elif (
            bot.units(UnitTypeId.QUEEN).amount + bot.already_pending(UnitTypeId.QUEEN) < bot.townhalls.amount
            and bot.structures(UnitTypeId.SPAWNINGPOOL).ready
        ):
            if bot.can_afford(UnitTypeId.QUEEN):
                bot.train(UnitTypeId.QUEEN)
        bot.register_behavior(Mining())

    def draw_creep_pixelmap(bot):
        for (y, x), value in np.ndenumerate(bot.state.creep.data_numpy):
            p = Point2((x, y))
            h2 = bot.get_terrain_z_height(p)
            pos = Point3((p.x, p.y, h2))
            # Red if there is no creep
            color = Point3((255, 0, 0))
            if value == 1:
                # Green if there is creep
                color = Point3((0, 255, 0))
            bot.client.debug_box2_out(pos, half_vertex_length=0.25, color=color)
    

class VsYuri:

    # pylint: disable=R0912
    async def on_step(self, bot, iteration):
        # Pick a target location
        target: Point2 = bot.enemy_start_locations[0]
        if iteration >= 3000:
            target = bot.enemy_structures[0]

        for worker in bot.units(UnitTypeId.DRONE):
            worker.attack(target)

class Tartarus(AresBot):
    def __init__(self, game_step_override: Optional[int] = None):
        super().__init__(game_step_override)
        self.on_end_called = False
        self.strategy = None

    async def on_start(self):
        await super(Tartarus, self).on_start()
        self.client.game_step = 2
        if self.opponent_id == "06e3d4d1-cb43-4324-bc7f-345033d8efbf":
            self.strategy = VsYuri()
        else:
            self.strategy = ZergRushBot()

    async def on_step(self, iteration):
        await super(Tartarus, self).on_step(iteration)
        if iteration == 2:
            await self.chat_send("glhf")

        await self.strategy.on_step(self, iteration)
    
    async def on_end(self, game_result: Result):
        self.on_end_called = True
        logger.info(f"{self.time_formatted} On end was called")



def main():
    run_game(
        maps.get("AcropolisLE"),
        [Bot(Race.Zerg, ZergRushBot()), Computer(Race.Terran, Difficulty.Medium)],
        realtime=False,
        save_replay_as="ZvT.SC2Replay",
    )


if __name__ == "__main__":
    main()

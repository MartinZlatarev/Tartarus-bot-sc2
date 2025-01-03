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
from ares.consts import UnitRole

# pylint: disable=W0231
class ZergRushBot:

    def __init__(self):
        self.currTarget = 0
        self.randoming = False
        self.attacking = False
        self.fighting = False
        self.makingZerglings = True
        self.target: Point2 = (0.0, 0.0)
        self.extractorMade = False
        self.secondExtractorMade = False
        self.extractorsMade = 0
        self.spireMade = False
        self.secondBaseMade = False
        self.decoyBaseMade = False
        self.savingUp = False
        self.hatch = None
        self.firstGeyser = None
        self.secondGeyser = None
        self.gas_drones = 0
        self.spineCrawlerCheeseDetected = False
        self.wave_length: dict = {
            "c033a97a-667d-42e3-91e8-13528ac191ed" : (40, True),
            "28a2fada-a646-4ba7-80b2-9c3dee593512" : (20, False),
            "4a491758-76ff-40de-996c-018d49b6237f" : (10, True),
            "60337090-fa15-485d-9497-d9b1c28a86b5" : (10, False),
            "anyoneElse" : (1, True)
        }

    # pylint: disable=R0912
    async def on_step(self, bot, iteration):
        # Draw creep pixelmap for debugging
        # self.draw_creep_pixelmap()

        #if iteration == 8000:
        #    bot.townhalls[0].upgrade(UP)

        # If townhall no longer exists: attack move with all units to enemy start location
        if not bot.townhalls:
            for unit in bot.units.exclude_type({UnitTypeId.EGG, UnitTypeId.LARVA}):
                unit.attack(bot.enemy_start_locations[0])
            return

        if self.hatch == None:
            self.hatch = bot.townhalls[0]
            temp = bot.vespene_geyser.closest_n_units(self.hatch, 2)
            self.firstGeyser = temp[0]
            self.secondGeyser = temp[1]
        
        for extractor in bot.units(UnitTypeId.EXTRACTOR):
            self.extractorsMade = self.extractorsMade+1

        if iteration == 2:
            enemy_main_ramp = min(
            bot.game_info.map_ramps, 
            key=lambda ramp: ramp.top_center.distance_to(Point2(bot.enemy_start_locations[0]))
            )
            self.target = enemy_main_ramp.top_center

        zerglings: int = 0
        for zergling in bot.units(UnitTypeId.ZERGLING):
            zerglings = zerglings+1
        mutalisks: int = 0
        for mutalisk in bot.units(UnitTypeId.MUTALISK):
            mutalisks = mutalisks+1

        key = None
        if bot.opponent_id in self.wave_length:
            key = bot.opponent_id
        else:
            key = "anyoneElse"
        
        if zerglings+mutalisks >= self.wave_length[key][0]:
            self.attacking = True
        else:
            self.attacking = False
        self.makingZerglings = self.wave_length[key][1]

        loc = min(bot.expansion_locations_list, key=lambda exp: exp.distance_to_point2((0, 0)))

        minDist2 = 1000
        for drone in bot.workers:
            minDist2 = min(minDist2, drone.distance_to(loc))

        if bot.opponent_id == "60337090-fa15-485d-9497-d9b1c28a86b5" and not self.savingUp and minDist2 <= 1:
            self.savingUp = True
        
        if minDist2 > 1:
            self.savingUp = False

        if bot.opponent_id == "60337090-fa15-485d-9497-d9b1c28a86b5" and not self.decoyBaseMade and self.spireMade:
            if worker := bot.mediator.select_worker(target_position=loc):
                bot.mediator.build_with_specific_worker(
                worker=worker, structure_type=UnitTypeId.HATCHERY, pos=loc
                )
                self.decoyBaseMade = True

        # Pick a target location

        minimumDist: int = 1000
        enemy_structure_count: int = 0
        for enemy_structure in bot.enemy_structures:
            enemy_structure_count = enemy_structure_count+1
        for zergling in bot.units(UnitTypeId.ZERGLING):
            minimumDist = min(minimumDist, zergling.distance_to(self.target))
        for mutalisk in bot.units(UnitTypeId.MUTALISK):
            minimumDist = min(minimumDist, mutalisk.distance_to(self.target))
        if minimumDist < 10:
            self.fighting = True
        else:
            self.fighting = False
        if enemy_structure_count == 0 and self.fighting:
            enemy_main_ramp = min(
            bot.game_info.map_ramps, 
            key=lambda ramp: ramp.top_center.distance_to(Point2(bot.enemy_start_locations[0]))
            )
            if self.target == enemy_main_ramp.top_center:
                self.target = bot.enemy_start_locations[0]
            else:
                self.randoming = True
                self.fighting = False


        # Give all zerglings an attack command
        
        if zerglings >= 100:
            self.makingZerglings = False
        if self.makingZerglings == False:
            if(bot.gas_buildings.ready):
                self.gas_drones = 3
            if not self.secondExtractorMade and bot.already_pending(UnitTypeId.EXTRACTOR)+bot.structures(UnitTypeId.EXTRACTOR).amount == 1 and bot.can_afford(UnitTypeId.EXTRACTOR) and bot.workers and not self.savingUp:
                loc: Point2 = self.secondGeyser
                if worker := bot.mediator.select_worker(target_position=loc):
                    bot.mediator.build_with_specific_worker(
                    worker=worker, structure_type=UnitTypeId.EXTRACTOR, pos=loc
                    )
                    self.secondExtractorMade = True
            if bot.structures(UnitTypeId.LAIR).amount + bot.already_pending(UnitTypeId.LAIR) == 0 and bot.can_afford(UnitTypeId.LAIR) and self.hatch.is_idle and not self.savingUp:
                bot.do(self.hatch(AbilityId.UPGRADETOLAIR_LAIR))
            if bot.structures(UnitTypeId.LAIR).ready.exists and not self.spireMade and bot.can_afford(UnitTypeId.SPIRE) and not self.savingUp:
                for d in range(5, 15):
                    loc: Point2 = self.hatch.position.towards(bot.game_info.map_center, d).offset((3, 0))
                    if await bot.can_place_single(UnitTypeId.SPIRE, loc):
                        if worker := bot.mediator.select_worker(target_position=loc):
                            bot.mediator.build_with_specific_worker(
                            worker=worker, structure_type=UnitTypeId.SPIRE, pos=loc
                            )
                            self.spireMade = True
                            break
            if bot.structures(UnitTypeId.SPIRE).ready.exists and bot.can_afford(UnitTypeId.MUTALISK) and not self.savingUp:
                bot.train(UnitTypeId.MUTALISK)

        if not self.randoming and self.attacking:
            if minimumDist < 3 and enemy_structure_count > 0:
                self.target = bot.enemy_structures[0].position
            for zergling in bot.units(UnitTypeId.ZERGLING):
                zergling.attack(self.target)
            for mutalisk in bot.units(UnitTypeId.MUTALISK):
                mutalisk.attack(self.target)
        elif self.randoming:
            for zergling in bot.units(UnitTypeId.ZERGLING):
                currTarget = zergling.order_target
                hasTarget = False
                if isinstance(currTarget, int):
                    rPos: Point2 = bot.expansion_locations_list[random.randrange(0, len(bot.expansion_locations_list)-1)]
                    zergling.attack(rPos)
                    hasTarget = True
                if not hasTarget and (zergling.is_idle or zergling.distance_to(currTarget) < 3):
                    rPos: Point2 = bot.expansion_locations_list[random.randrange(0, len(bot.expansion_locations_list)-1)]
                    zergling.attack(rPos)
            for mutalisk in bot.units(UnitTypeId.MUTALISK):
                if not mutalisk.is_active:
                    map_width = bot.game_info.map_size[0]
                    map_height = bot.game_info.map_size[1]
                    
                    random_x = random.uniform(0, map_width)
                    random_y = random.uniform(0, map_height)
                    random_position = Point2((random_x, random_y))
                    mutalisk.attack(random_position)
            if enemy_structure_count > 0:
                self.target = bot.enemy_structures[0].position
                self.randoming = False
                self.fighting = True
            
        # Inject hatchery if queen has more than 25 energy
        if self.makingZerglings:
            for queen in bot.units(UnitTypeId.QUEEN):
                if queen.energy >= 25 and not self.hatch.has_buff(BuffId.QUEENSPAWNLARVATIMER):
                    queen(AbilityId.EFFECT_INJECTLARVA, self.hatch)
        
        # Pull workers out of gas if we have almost enough gas mined, this will stop mining when we reached 100 gas mined
        if self.makingZerglings:
            if bot.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED) > 0:
                self.gas_drones = 0
                        
        
        # If we have 100 vespene, this will try to research zergling speed once the spawning pool is at 100% completion
        if bot.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED
                                        ) == 0 and bot.can_afford(UpgradeId.ZERGLINGMOVEMENTSPEED) and self.makingZerglings:
            spawning_pools_ready: Units = bot.structures(UnitTypeId.SPAWNINGPOOL).ready
            if spawning_pools_ready:
                bot.research(UpgradeId.ZERGLINGMOVEMENTSPEED)

        # If we have less than 2 supply left and no overlord is in the queue: train an overlord
        if bot.supply_left < 2 and bot.already_pending(UnitTypeId.OVERLORD) < 1:
            bot.train(UnitTypeId.OVERLORD, 1)

        # While we have less than 88 vespene mined: send drones into extractor one frame at a time
        if (
            bot.gas_buildings.ready and bot.vespene < 88
            and bot.already_pending_upgrade(UpgradeId.ZERGLINGMOVEMENTSPEED) == 0 and not self.savingUp
        ):
            self.gas_drones = 3

        # If we have lots of minerals, make a macro hatchery
        if bot.minerals > 500 and self.secondBaseMade == False and self.makingZerglings == True and not self.savingUp:
            for d in range(9, 15):
                loc: Point2 = self.hatch.position.towards(bot.game_info.map_center, d)
                if await bot.can_place_single(UnitTypeId.HATCHERY, loc):
                    if worker := bot.mediator.select_worker(target_position=loc):
                        bot.mediator.build_with_specific_worker(
                        worker=worker, structure_type=UnitTypeId.HATCHERY, pos=loc
                        )
                        self.secondBaseMade = True
                        break

        # While we have less than 16 drones, make more drones
        if bot.can_afford(UnitTypeId.DRONE) and bot.supply_workers+bot.already_pending(UnitTypeId.DRONE) < 16 and bot.structures(UnitTypeId.SPAWNINGPOOL).amount > 0 and not self.savingUp:
            bot.train(UnitTypeId.DRONE)
        
        # If our spawningpool is completed, start making zerglings
        
        if self.makingZerglings and self.makingZerglings and bot.structures(UnitTypeId.SPAWNINGPOOL).ready and bot.larva and bot.can_afford(UnitTypeId.ZERGLING) and not self.savingUp:
            _amount_trained: int = bot.train(UnitTypeId.ZERGLING, bot.larva.amount)

        # If we have no spawning pool, try to build spawning pool
        if bot.structures(UnitTypeId.SPAWNINGPOOL).amount + bot.already_pending(UnitTypeId.SPAWNINGPOOL) == 0 and not self.savingUp:
            if bot.can_afford(UnitTypeId.SPAWNINGPOOL):
                for d in range(4, 15):
                    loc: Point2 = self.hatch.position.towards(bot.game_info.map_center, d)
                    if await bot.can_place_single(UnitTypeId.SPAWNINGPOOL, loc):
                        if worker := bot.mediator.select_worker(target_position=loc):
                            bot.mediator.build_with_specific_worker(
                            worker=worker, structure_type=UnitTypeId.SPAWNINGPOOL, pos=loc
                            )
                            break

        # If we have no extractor, build extractor
        elif (not self.extractorMade and bot.can_afford(UnitTypeId.EXTRACTOR) and bot.workers and not self.savingUp):
            loc: Point2 = self.firstGeyser
            if worker := bot.mediator.select_worker(target_position=loc):
                bot.mediator.build_with_specific_worker(
                worker=worker, structure_type=UnitTypeId.EXTRACTOR, pos=loc
                )   
                self.extractorMade = True


        # If we have no queen, try to build a queen if we have a spawning pool compelted
        elif (
            self.makingZerglings and bot.units(UnitTypeId.QUEEN).amount + bot.already_pending(UnitTypeId.QUEEN) < bot.townhalls.amount
            and bot.structures(UnitTypeId.SPAWNINGPOOL).ready
        ):
            if bot.can_afford(UnitTypeId.QUEEN) and not self.savingUp:
                bot.train(UnitTypeId.QUEEN)
        
        spine_crawler_amount = 0
        for spinecrawler in bot.enemy_structures(UnitTypeId.SPINECRAWLER):
            if spinecrawler.distance_to(self.hatch) < 11:
                self.spineCrawlerCheeseDetected = True
                spine_crawler_amount = spine_crawler_amount+1
                for drone in bot.workers:
                    bot.mediator.assign_role(tag = drone.tag, role = UnitRole.DEFENDING)
                    drone.attack(spinecrawler.position)
        if spine_crawler_amount == 0 and self.spineCrawlerCheeseDetected:
            self.spineCrawlerCheeseDetected = False
            for drone in bot.workers:
                bot.mediator.assign_role(tag = drone.tag, role = UnitRole.GATHERING)

        bot.register_behavior(Mining(workers_per_gas=self.gas_drones))

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
